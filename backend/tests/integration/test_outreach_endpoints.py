import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.kernel import SlidingWindowRateLimiter
from hiresense.outreach.api import router as outreach_router
from hiresense.outreach.api.dependencies import get_outreach_service
from hiresense.outreach.domain import OutreachMessageGenerator, OutreachService
from hiresense.outreach.infrastructure import OutreachRepository
from hiresense.outreach.infrastructure.orm import OutreachEventOrm  # noqa: F401


class _StubSender:
    def send(self, message) -> None:  # matches EmailSender port
        return None


class _FakeLLM:
    async def complete(self, prompt, system):
        return "Hi Sam, I'd love to connect about the role."


class _Tracking:
    def __init__(self, apps):
        self._apps = {a.id: a for a in apps}

    def get(self, app_id):
        if app_id not in self._apps:
            raise ValueError("not found")
        return self._apps[app_id]


class _App:
    def __init__(self, id, company="Acme", status="applied"):
        self.id = id
        self.company = company
        self.title = "Backend Engineer"
        self.status = status
        self.url = None
        self.notes = "Build APIs"


class _Profile:
    async def get_current_profile(self, language=None):
        return type("P", (), {"name": "Bryan"})()

    def get_for_language(self, language):
        return type("V", (), {"skills": ["python"], "summary": "dev"})()


class _Research:
    def get(self, company):
        return None


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False), engine


def _build_app(app_id, factory, *, limiter=None):
    repo = OutreachRepository(session_factory=factory)
    service = OutreachService(
        tracking_service=_Tracking([_App(app_id)]),
        profile_service=_Profile(),
        research_service=_Research(),
        generator=OutreachMessageGenerator(llm=_FakeLLM()),
        repo=repo,
        style_guide_path="does/not/exist.md",
        followup_cadence_days=7,
        max_chars=500,
        language="en",
        sender=_StubSender(),
    )
    app = FastAPI()
    app.state.rate_limiter = limiter
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_outreach_service] = lambda: service
    app.include_router(outreach_router)
    return app


@pytest.mark.asyncio
async def test_generate_record_list_flow():
    factory, _ = _factory()
    app_id = uuid_mod.uuid4()
    app = _build_app(app_id, factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        gen = await c.post(
            "/outreach/generate", json={"application_id": str(app_id), "contact_name": "Sam"}
        )
        assert gen.status_code == 200
        assert "connect" in gen.json()["message"]

        rec = await c.post(
            "/outreach/record",
            json={
                "application_id": str(app_id),
                "kind": "sent",
                "message": gen.json()["message"],
                "contact_name": "Sam",
            },
        )
        assert rec.status_code == 201

        events = await c.get(f"/outreach/events?application_id={app_id}")
        assert events.status_code == 200 and len(events.json()) == 1


@pytest.mark.asyncio
async def test_nudge_surfaces_then_clears():
    factory, engine = _factory()
    app_id = uuid_mod.uuid4()
    app = _build_app(app_id, factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post(
            "/outreach/record",
            json={"application_id": str(app_id), "kind": "sent", "message": "hi"},
        )
        # Back-date the sent event past the cadence so the nudge is due.
        with factory() as s:
            s.execute(
                update(OutreachEventOrm)
                .where(OutreachEventOrm.application_id == app_id)
                .values(created_at=datetime.now(timezone.utc) - timedelta(days=10))
            )
            s.commit()
        due = await c.post("/outreach/nudge")
        assert due.status_code == 200
        assert [n["application_id"] for n in due.json()] == [str(app_id)]

        # Recording a reply clears the nudge (latest event is no longer 'sent').
        await c.post("/outreach/record", json={"application_id": str(app_id), "kind": "replied"})
        cleared = await c.post("/outreach/nudge")
        assert cleared.json() == []


@pytest.mark.asyncio
async def test_send_rejects_invalid_email_recipient():
    factory, _ = _factory()
    app_id = uuid_mod.uuid4()
    app = _build_app(app_id, factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post(
            "/outreach/send",
            json={
                "application_id": str(app_id),
                "to": "not-an-email",
                "subject": "Hello",
                "message": "Body",
            },
        )
        assert resp.status_code == 422  # EmailStr validation rejects malformed recipient


@pytest.mark.asyncio
async def test_send_is_rate_limited():
    factory, _ = _factory()
    app_id = uuid_mod.uuid4()
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    app = _build_app(app_id, factory, limiter=limiter)
    payload = {
        "application_id": str(app_id),
        "to": "recruiter@acme.com",
        "subject": "Hello",
        "message": "Body",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        first = await c.post("/outreach/send", json=payload)
        assert first.status_code == 201
        second = await c.post("/outreach/send", json=payload)
        assert second.status_code == 429

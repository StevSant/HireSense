import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.identity.api.dependencies import require_admin, require_auth
from hiresense.shared.infrastructure import registry  # noqa: F401
from hiresense.shared.infrastructure.database import Base
from hiresense.submission.api import router as submission_router
from hiresense.submission.api.dependencies import get_submission_provider
from hiresense.submission.api.provider import SubmissionProvider
from hiresense.submission.domain import (
    AgentContext,
    EscalateAction,
    SubmissionService,
    SubmissionStatus,
    SubmitAction,
)
from hiresense.submission.infrastructure import SubmissionRepositoryImpl


class _Agent:
    def __init__(self, action=None):
        self.action = action or SubmitAction(selector="#go", dry_run=True)

    async def next_action(self, *, observation, context):
        return self.action


class _Bank:
    def __init__(self):
        self.remembered = []

    async def remember(self, answers):
        self.remembered.extend(answers)


class _ContextBuilder:
    async def build(self, attempt):
        return AgentContext()


@pytest.fixture()
def harness():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    repo = SubmissionRepositoryImpl(session_factory=sessionmaker(bind=engine))
    bank = _Bank()

    def build(action=None, daily_cap=10):
        service = SubmissionService(
            repo,
            _Agent(action),
            bank,
            daily_cap=daily_cap,
            lease_seconds=300,
            max_attempts=2,
        )
        app = FastAPI()
        provider = SubmissionProvider(service=service, repo=repo, context_builder=_ContextBuilder())
        app.dependency_overrides[get_submission_provider] = lambda: provider
        app.dependency_overrides[require_auth] = lambda: {"sub": "u"}
        app.dependency_overrides[require_admin] = lambda: {"sub": "admin"}
        app.include_router(submission_router)
        return app, service

    return build, repo, bank


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


def _enqueue_body(**kw):
    body = {
        "application_id": str(uuid.uuid4()),
        "job_id": "job-1",
        "packet_id": str(uuid.uuid4()),
        "channel": "ats_form",
        "target_url": "https://boards.greenhouse.io/acme/jobs/1",
    }
    body.update(kw)
    return body


async def test_enqueue_then_lease_then_observe(harness):
    build, repo, _ = harness
    app, _ = build()
    async with _client(app) as client:
        created = await client.post("/submission/enqueue", json=_enqueue_body())
        assert created.status_code == 201

        leased = await client.post("/submission/lease", json={"runner_id": "r1", "capacity": 5})
        assert leased.status_code == 200
        assert len(leased.json()) == 1
        attempt_id = leased.json()[0]["id"]
        assert leased.json()[0]["status"] == SubmissionStatus.CLAIMED.value

        observed = await client.post(
            f"/submission/attempts/{attempt_id}/observe",
            json={
                "observation": {
                    "url": "https://boards.greenhouse.io/acme/jobs/1",
                    "title": "Apply",
                    "fields": [],
                }
            },
        )
        assert observed.status_code == 200
        assert observed.json()["kind"] == "submit"
        assert observed.json()["dry_run"] is True


async def test_enqueue_beyond_the_daily_cap_returns_409(harness):
    build, _, _ = harness
    app, _ = build(daily_cap=1)
    async with _client(app) as client:
        assert (await client.post("/submission/enqueue", json=_enqueue_body())).status_code == 201
        second = await client.post("/submission/enqueue", json=_enqueue_body())
    assert second.status_code == 409
    assert "cap" in second.json()["detail"].lower()


async def test_duplicate_live_attempt_returns_409(harness):
    build, _, _ = harness
    app, _ = build()
    app_id = str(uuid.uuid4())
    async with _client(app) as client:
        await client.post("/submission/enqueue", json=_enqueue_body(application_id=app_id))
        second = await client.post("/submission/enqueue", json=_enqueue_body(application_id=app_id))
    assert second.status_code == 409


async def test_escalated_attempts_are_listable_and_resumable(harness):
    build, repo, bank = harness
    app, _ = build(action=EscalateAction(reason="Desired salary", fields=["#salary"]))
    async with _client(app) as client:
        created = await client.post("/submission/enqueue", json=_enqueue_body())
        attempt_id = created.json()["id"]
        await client.post("/submission/lease", json={"runner_id": "r1", "capacity": 5})
        await client.post(
            f"/submission/attempts/{attempt_id}/observe",
            json={"observation": {"url": "https://x.test", "title": "t", "fields": []}},
        )

        listed = await client.get("/submission/attempts", params={"status": "escalated"})
        assert [a["id"] for a in listed.json()] == [attempt_id]
        assert listed.json()[0]["escalated_fields"] == ["#salary"]

        resumed = await client.post(
            f"/submission/attempts/{attempt_id}/resume",
            json={"answers": {"Desired salary": "70000 EUR"}},
        )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == SubmissionStatus.QUEUED.value
    assert bank.remembered == [("Desired salary", "70000 EUR")]


async def test_audit_tape_is_readable(harness):
    build, _, _ = harness
    app, _ = build()
    async with _client(app) as client:
        created = await client.post("/submission/enqueue", json=_enqueue_body())
        attempt_id = created.json()["id"]
        await client.post("/submission/lease", json={"runner_id": "r1", "capacity": 5})
        await client.post(
            f"/submission/attempts/{attempt_id}/observe",
            json={"observation": {"url": "https://x.test", "title": "t", "fields": []}},
        )
        events = await client.get(f"/submission/attempts/{attempt_id}/events")
    assert events.status_code == 200
    assert [e["kind"] for e in events.json()] == ["submit"]


async def test_complete_records_evidence(harness):
    build, _, _ = harness
    app, _ = build()
    async with _client(app) as client:
        created = await client.post("/submission/enqueue", json=_enqueue_body())
        attempt_id = created.json()["id"]
        done = await client.post(
            f"/submission/attempts/{attempt_id}/complete",
            json={
                "status": "submitted",
                "evidence": {"final_url": "https://x.test/thanks"},
            },
        )
    assert done.status_code == 200
    assert done.json()["evidence"]["final_url"] == "https://x.test/thanks"


async def test_abandon_marks_terminal(harness):
    build, _, _ = harness
    app, _ = build()
    async with _client(app) as client:
        created = await client.post("/submission/enqueue", json=_enqueue_body())
        attempt_id = created.json()["id"]
        done = await client.post(f"/submission/attempts/{attempt_id}/abandon")
    assert done.json()["status"] == SubmissionStatus.ABANDONED.value


async def test_unknown_attempt_returns_404(harness):
    build, _, _ = harness
    app, _ = build()
    async with _client(app) as client:
        resp = await client.post(
            f"/submission/attempts/{uuid.uuid4()}/resume", json={"answers": {}}
        )
    assert resp.status_code == 404


async def test_heartbeat_extends_the_lease(harness):
    build, _, _ = harness
    app, _ = build()
    async with _client(app) as client:
        created = await client.post("/submission/enqueue", json=_enqueue_body())
        attempt_id = created.json()["id"]
        leased = await client.post("/submission/lease", json={"runner_id": "r1", "capacity": 5})
        before = leased.json()[0]["lease_expires_at"]
        beat = await client.post(f"/submission/attempts/{attempt_id}/heartbeat")
    assert beat.status_code == 200
    assert beat.json()["lease_expires_at"] >= before

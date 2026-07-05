import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.inbox.api import router as inbox_router
from hiresense.inbox.api.dependencies import get_inbox_provider
from hiresense.inbox.api.provider import InboxProvider
from hiresense.inbox.domain import (
    ApplicationMatcher,
    EmailClassification,
    EmailSignalKind,
    InboxProcessingService,
)
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class _Reader:
    def fetch_unseen(self):
        return []


class _Repo:
    def __init__(self):
        self.signals = []

    def add(self, s):
        s.id = uuid.uuid4()
        self.signals.append(s)
        return s

    def list(self, state=None):
        return [s for s in self.signals if state is None or s.state == state]

    def get(self, id):
        return next((s for s in self.signals if s.id == id), None)

    def set_state(self, id, state):
        s = self.get(id)
        s.state = state
        return s

    def exists_message_id(self, mid):
        return any(s.message_id == mid for s in self.signals)


class _Classifier:
    async def classify(self, email):
        return EmailClassification(
            job_related=True,
            kind=EmailSignalKind.REJECTION,
            company="Acme",
            role="Dev",
            confidence=0.9,
        )


class _Tracking:
    def __init__(self, app):
        self._app = app
        self.updated = []

    async def update_status(self, id, status, notes=None):
        self.updated.append((id, status))
        return self._app


def _build_app():
    app_model = TrackedApplication(
        id=uuid.uuid4(),
        title="Dev",
        company="Acme",
        status=ApplicationStatus.APPLIED.value,
    )
    repo = _Repo()
    service = InboxProcessingService(
        reader=_Reader(),
        repo=repo,
        classifier=_Classifier(),
        matcher=ApplicationMatcher(min_confidence=0.5),
        list_active=lambda: [app_model],
    )
    tracking = _Tracking(app_model)
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "u"
    app.dependency_overrides[get_inbox_provider] = lambda: InboxProvider(service=service, repo=repo)
    app.dependency_overrides[get_tracking_service] = lambda: tracking
    app.include_router(inbox_router)
    return app, repo, tracking, app_model


@pytest.mark.asyncio
async def test_ingest_then_confirm_updates_status():
    app, repo, tracking, app_model = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.post(
            "/tracking/ingest-email",
            json={"from_address": "r@acme.com", "subject": "Update", "body": "We regret..."},
        )
        assert r.status_code == 201
        sig = r.json()
        assert sig["proposed_status"] == "rejected"

        lst = await client.get("/inbox/signals?state=pending")
        assert len(lst.json()) == 1

        conf = await client.post(f"/inbox/signals/{sig['id']}/confirm")
        assert conf.status_code == 200
    assert tracking.updated[0][1] == ApplicationStatus.REJECTED
    assert repo.get(uuid.UUID(sig["id"])).state.value == "applied"


@pytest.mark.asyncio
async def test_confirm_unmatched_returns_409():
    app, repo, tracking, _ = _build_app()
    from hiresense.inbox.domain import DetectedSignal

    sig = repo.add(
        DetectedSignal(
            message_id="x",
            from_address="a@b.com",
            subject="s",
            received_at=datetime.now(timezone.utc),
            kind=EmailSignalKind.OTHER,
            matched_application_id=None,
            proposed_status=None,
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        conf = await client.post(f"/inbox/signals/{sig.id}/confirm")
    assert conf.status_code == 409


@pytest.mark.asyncio
async def test_dismiss_sets_state():
    app, repo, tracking, _ = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.post(
            "/tracking/ingest-email",
            json={"from_address": "r@acme.com", "subject": "Update", "body": "We regret..."},
        )
        sid = r.json()["id"]
        d = await client.post(f"/inbox/signals/{sid}/dismiss")
        assert d.status_code == 200
    assert repo.get(uuid.UUID(sid)).state.value == "dismissed"

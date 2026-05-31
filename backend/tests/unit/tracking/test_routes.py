from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.ingestion.api.dependencies import get_ingestion_orchestrator
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.api.routes import router
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class FakeOrchestrator:
    def get_job_by_id(self, job_id: str):
        return None


# ---------------------------------------------------------------------------
# Fake service
# ---------------------------------------------------------------------------


class FakeTrackingService:
    def __init__(self) -> None:
        self._store: dict[uuid_mod.UUID, TrackedApplication] = {}

    def _make(self, **kwargs) -> TrackedApplication:
        app = TrackedApplication(**kwargs)
        if app.id is None:
            app.id = uuid_mod.uuid4()
        now = datetime.now(timezone.utc)
        if app.created_at is None:
            app.created_at = now
        if app.updated_at is None:
            app.updated_at = now
        self._store[app.id] = app
        return app

    def track_job(
        self,
        title: str,
        company: str,
        url: str | None = None,
        notes: str | None = None,
    ) -> TrackedApplication:
        return self._make(title=title, company=company, url=url, notes=notes)

    def track_from_ingestion(self, job_id: str) -> TrackedApplication:
        raise ValueError(f"Job {job_id} not found")

    def get(self, id: uuid_mod.UUID) -> TrackedApplication:
        app = self._store.get(id)
        if app is None:
            raise ValueError(f"Application {id} not found")
        return app

    def list(self, status: ApplicationStatus | None = None) -> list[TrackedApplication]:
        apps = list(self._store.values())
        if status is not None:
            apps = [a for a in apps if a.status == status.value]
        return apps

    async def update_status(
        self,
        id: uuid_mod.UUID,
        status: ApplicationStatus,
        notes: str | None = None,
    ) -> TrackedApplication:
        app = self.get(id)
        app.status = status.value
        if notes is not None:
            app.notes = notes
        app.updated_at = datetime.now(timezone.utc)
        return app

    def update_notes(self, id: uuid_mod.UUID, notes: str) -> TrackedApplication:
        app = self.get(id)
        app.notes = notes
        app.updated_at = datetime.now(timezone.utc)
        return app

    def remove(self, id: uuid_mod.UUID) -> None:
        if id not in self._store:
            raise ValueError(f"Application {id} not found")
        del self._store[id]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(fake: FakeTrackingService) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_tracking_service] = lambda: fake
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: FakeOrchestrator()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_manual_application() -> None:
    fake = FakeTrackingService()
    client = TestClient(make_app(fake))

    resp = client.post("/tracking", json={"title": "Backend Engineer", "company": "Acme"})

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Backend Engineer"
    assert data["company"] == "Acme"
    assert data["status"] == ApplicationStatus.SAVED.value


def test_create_from_ingestion_not_found() -> None:
    fake = FakeTrackingService()
    client = TestClient(make_app(fake))

    resp = client.post("/tracking", json={"job_id": str(uuid_mod.uuid4())})

    assert resp.status_code == 404


def test_list_applications() -> None:
    fake = FakeTrackingService()
    fake.track_job(title="Job A", company="Co A")
    fake.track_job(title="Job B", company="Co B")
    client = TestClient(make_app(fake))

    resp = client.get("/tracking")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_get_application() -> None:
    fake = FakeTrackingService()
    created = fake.track_job(title="DevOps", company="Stripe")
    client = TestClient(make_app(fake))

    resp = client.get(f"/tracking/{created.id}")

    assert resp.status_code == 200
    assert resp.json()["title"] == "DevOps"


def test_get_application_not_found() -> None:
    fake = FakeTrackingService()
    client = TestClient(make_app(fake))

    resp = client.get(f"/tracking/{uuid_mod.uuid4()}")

    assert resp.status_code == 404


def test_update_application() -> None:
    fake = FakeTrackingService()
    created = fake.track_job(title="ML Engineer", company="DeepMind")
    client = TestClient(make_app(fake))

    resp = client.patch(
        f"/tracking/{created.id}",
        json={"status": ApplicationStatus.APPLIED.value},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == ApplicationStatus.APPLIED.value


def test_update_application_not_found() -> None:
    fake = FakeTrackingService()
    client = TestClient(make_app(fake))

    resp = client.patch(
        f"/tracking/{uuid_mod.uuid4()}",
        json={"status": ApplicationStatus.APPLIED.value},
    )

    assert resp.status_code == 404


def test_delete_application() -> None:
    fake = FakeTrackingService()
    created = fake.track_job(title="QA Engineer", company="Atlassian")
    client = TestClient(make_app(fake))

    resp = client.delete(f"/tracking/{created.id}")

    assert resp.status_code == 204


def test_delete_application_not_found() -> None:
    fake = FakeTrackingService()
    client = TestClient(make_app(fake))

    resp = client.delete(f"/tracking/{uuid_mod.uuid4()}")

    assert resp.status_code == 404

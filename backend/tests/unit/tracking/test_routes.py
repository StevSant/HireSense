from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.ingestion.api.dependencies import get_ingestion_orchestrator
from hiresense.kernel import register_domain_exception_handlers
from hiresense.kernel.exceptions import ConflictError, NotFoundError
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.api.routes import router
from hiresense.tracking.domain import InvalidStatusTransitionError
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
        self.update_application_calls = 0
        self.update_status_calls = 0
        self.update_details_calls = 0

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
        **metadata,
    ) -> TrackedApplication:
        return self._make(title=title, company=company, url=url, notes=notes, **metadata)

    def track_from_ingestion(self, job_id: str) -> TrackedApplication:
        raise NotFoundError(f"Job {job_id} not found")

    def get(self, id: uuid_mod.UUID) -> TrackedApplication:
        app = self._store.get(id)
        if app is None:
            raise ValueError(f"Application {id} not found")
        return app

    def list(
        self,
        status: ApplicationStatus | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackedApplication]:
        apps = list(self._store.values())
        if status is not None:
            apps = [a for a in apps if a.status == status.value]
        if offset:
            apps = apps[offset:]
        if limit is not None:
            apps = apps[:limit]
        return apps

    def count(self, status: ApplicationStatus | None = None) -> int:
        apps = list(self._store.values())
        if status is not None:
            apps = [a for a in apps if a.status == status.value]
        return len(apps)

    async def update_status(
        self,
        id: uuid_mod.UUID,
        status: ApplicationStatus,
        notes: str | None = None,
    ) -> TrackedApplication:
        self.update_status_calls += 1
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

    def update_details(self, id: uuid_mod.UUID, changes: dict) -> TrackedApplication:
        self.update_details_calls += 1
        app = self.get(id)
        for field, value in changes.items():
            setattr(app, field, value)
        app.updated_at = datetime.now(timezone.utc)
        return app

    async def update_application(
        self,
        id: uuid_mod.UUID,
        *,
        status: ApplicationStatus | None = None,
        changes: dict[str, object | None] | None = None,
    ) -> TrackedApplication:
        self.update_application_calls += 1
        app = self.get(id)
        if status is not None:
            app.status = status.value
        for field, value in (changes or {}).items():
            setattr(app, field, value)
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
    register_domain_exception_handlers(app)
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


def test_create_manual_application_with_listing_metadata() -> None:
    client = TestClient(make_app(FakeTrackingService()))

    resp = client.post(
        "/tracking",
        json={
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Quito",
            "remote_modality": "onsite",
            "salary_range": "USD 1,500-2,000/mo",
            "source": "Referral",
            "posted_date": "2026-07-01T00:00:00Z",
        },
    )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["location"] == "Quito"
    assert data["remote_modality"] == "on_site"
    assert data["salary_range"] == "USD 1,500-2,000/mo"
    assert data["source"] == "Referral"


def test_create_from_ingestion_not_found() -> None:
    fake = FakeTrackingService()
    client = TestClient(make_app(fake))

    resp = client.post("/tracking", json={"job_id": str(uuid_mod.uuid4())})

    assert resp.status_code == 404


def test_create_from_ingestion_already_tracked_returns_409() -> None:
    """A ConflictError from the service maps to HTTP 409 via the shared handler,
    with no message-substring inspection in the router."""
    fake = FakeTrackingService()
    fake.track_from_ingestion = lambda job_id: (_ for _ in ()).throw(  # type: ignore[assignment]
        ConflictError("This job is already tracked")
    )
    client = TestClient(make_app(fake))

    resp = client.post("/tracking", json={"job_id": str(uuid_mod.uuid4())})

    assert resp.status_code == 409
    assert resp.json()["detail"] == "This job is already tracked"


def test_list_applications() -> None:
    fake = FakeTrackingService()
    fake.track_job(title="Job A", company="Co A")
    fake.track_job(title="Job B", company="Co B")
    client = TestClient(make_app(fake))

    resp = client.get("/tracking")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_list_applications_paginates_and_reports_total() -> None:
    fake = FakeTrackingService()
    for i in range(3):
        fake.track_job(title=f"Job {i}", company="Co")
    client = TestClient(make_app(fake))

    first = client.get("/tracking", params={"limit": 2, "offset": 0})
    assert first.status_code == 200
    assert len(first.json()) == 2
    assert first.headers["X-Total-Count"] == "3"

    second = client.get("/tracking", params={"limit": 2, "offset": 2})
    assert len(second.json()) == 1
    assert second.headers["X-Total-Count"] == "3"


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


def test_update_application_details_preserves_omitted_and_clears_null() -> None:
    fake = FakeTrackingService()
    created = fake.track_job(
        title="ML Engineer",
        company="DeepMind",
        location="London",
        salary_range="GBP 90,000/year",
    )
    client = TestClient(make_app(fake))

    resp = client.patch(
        f"/tracking/{created.id}",
        json={"title": "Senior ML Engineer", "location": None, "remote_modality": "hybrid"},
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"] == "Senior ML Engineer"
    assert data["location"] is None
    assert data["remote_modality"] == "hybrid"
    assert data["salary_range"] == "GBP 90,000/year"


def test_combined_update_calls_atomic_service_operation_once() -> None:
    fake = FakeTrackingService()
    created = fake.track_job(title="ML Engineer", company="DeepMind")
    client = TestClient(make_app(fake))

    response = client.patch(
        f"/tracking/{created.id}",
        json={"status": "applied", "title": "Senior ML Engineer", "source": "Referral"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"
    assert response.json()["title"] == "Senior ML Engineer"
    assert fake.update_application_calls == 1
    assert fake.update_status_calls == 0
    assert fake.update_details_calls == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "t" * 256),
        ("company", "c" * 256),
        ("url", f"https://example.com/{'u' * 2030}"),
        ("source", "s" * 101),
    ],
)
def test_update_rejects_values_larger_than_tracking_columns(field: str, value: str) -> None:
    fake = FakeTrackingService()
    created = fake.track_job(title="ML Engineer", company="DeepMind")
    client = TestClient(make_app(fake))

    response = client.patch(f"/tracking/{created.id}", json={field: value})

    assert response.status_code == 422


def test_update_application_rejects_invalid_remote_modality() -> None:
    fake = FakeTrackingService()
    created = fake.track_job(title="ML Engineer", company="DeepMind")
    client = TestClient(make_app(fake))

    resp = client.patch(
        f"/tracking/{created.id}",
        json={"remote_modality": "sometimes"},
    )

    assert resp.status_code == 422


def test_update_application_not_found() -> None:
    fake = FakeTrackingService()
    client = TestClient(make_app(fake))

    resp = client.patch(
        f"/tracking/{uuid_mod.uuid4()}",
        json={"status": ApplicationStatus.APPLIED.value},
    )

    assert resp.status_code == 404


class _RejectingTransitionService(FakeTrackingService):
    async def update_application(self, id, *, status=None, changes=None):
        raise InvalidStatusTransitionError("Cannot change status")


def test_update_application_invalid_transition_returns_409() -> None:
    fake = _RejectingTransitionService()
    created = fake.track_job(title="ML Engineer", company="DeepMind")
    client = TestClient(make_app(fake))

    resp = client.patch(
        f"/tracking/{created.id}",
        json={"status": ApplicationStatus.SAVED.value},
    )

    assert resp.status_code == 409


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

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.applications.api.dependencies import (
    get_application_service,
    get_apply_service,
    get_artifact_service,
)
from hiresense.applications.api.routes import router
from hiresense.applications.domain.aggregate import (
    ApplicationAggregate,
    InterviewPrepView,
    JobSnapshotView,
    MatchView,
)
from hiresense.identity.api.dependencies import require_auth
from hiresense.ingestion.api.dependencies import get_ingestion_orchestrator
from hiresense.kernel import SlidingWindowRateLimiter, register_domain_exception_handlers
from hiresense.kernel.exceptions import ConflictError, NotFoundError, ValidationError
from hiresense.tracking.domain import InvalidStatusTransitionError


class FakeOrchestrator:
    """List enrichment looks up the linked ingested job; manual apps have none."""

    def get_job_by_id(self, job_id: str):
        return None

    jobs_by_id: dict[str, object] = {}

    def get_jobs_by_ids(self, job_ids):
        return {job_id: self.jobs_by_id[job_id] for job_id in job_ids if job_id in self.jobs_by_id}


def _make_aggregate(
    *,
    title: str = "Software Engineer",
    company: str = "Fieldguide",
    description: str = "job desc",
    required_skills: list[str] | None = None,
    match_count: int = 0,
    latest_match_score: float | None = None,
    job_id: uuid_mod.UUID | None = None,
    location: str | None = None,
    remote_modality: str | None = None,
    salary_range: str | None = None,
    source: str | None = None,
    posted_date: datetime | None = None,
) -> ApplicationAggregate:
    app_id = uuid_mod.uuid4()
    now = datetime.now(timezone.utc)
    snap = JobSnapshotView(
        id=uuid_mod.uuid4(),
        description=description,
        required_skills=required_skills or [],
        source="manual",
        updated_at=now,
    )
    latest_match: MatchView | None = None
    if latest_match_score is not None:
        latest_match = MatchView(
            id=uuid_mod.uuid4(),
            overall_score=latest_match_score,
            semantic_score=latest_match_score,
            skill_score=latest_match_score,
            experience_score=latest_match_score,
            language_score=latest_match_score,
            matched_skills=[],
            missing_skills=[],
            pros=[],
            cons=[],
            recommendations=[],
            cv_language="en",
            created_at=now,
        )
    return ApplicationAggregate(
        id=app_id,
        job_id=job_id,
        title=title,
        company=company,
        url=None,
        status="saved",
        notes=None,
        applied_at=None,
        created_at=now,
        updated_at=now,
        location=location,
        remote_modality=remote_modality,
        salary_range=salary_range,
        source=source,
        posted_date=posted_date,
        job_snapshot=snap,
        latest_match=latest_match,
        latest_optimization=None,
        latest_interview_prep=None,
        match_count=match_count,
        optimization_count=0,
        interview_prep_count=0,
    )


class FakeApplicationService:
    def __init__(self) -> None:
        self._store: dict[uuid_mod.UUID, ApplicationAggregate] = {}

    async def create_from_manual(self, title, company, description, url, notes=None, **metadata):
        agg = _make_aggregate(
            title=title,
            company=company,
            description=description,
            **metadata,
        )
        self._store[agg.id] = agg
        return agg

    async def create_from_ingested(self, job_id):
        raise NotFoundError(f"Job {job_id} not found")

    def get(self, application_id):
        agg = self._store.get(application_id)
        if agg is None:
            raise ValueError(f"Application {application_id} not found")
        return agg

    def list(self, status=None, *, limit=None, offset=None):
        apps = list(self._store.values())
        if offset:
            apps = apps[offset:]
        if limit is not None:
            apps = apps[:limit]
        return apps

    def count(self, status=None):
        return len(self._store)

    def list_all_cover_letters(self, *, limit=None, offset=None):
        return []

    def count_all_cover_letters(self):
        return 0

    def remove(self, application_id):
        if application_id not in self._store:
            raise ValueError(f"Application {application_id} not found")
        del self._store[application_id]

    def update_snapshot(self, application_id, description=None, required_skills=None):
        agg = self.get(application_id)
        if agg.job_snapshot is None:
            raise ValueError("no snapshot")
        if description is not None:
            agg.job_snapshot.description = description
        if required_skills is not None:
            agg.job_snapshot.required_skills = required_skills
        return agg

    async def regenerate_skills(self, application_id):
        agg = self.get(application_id)
        if agg.job_snapshot is not None:
            agg.job_snapshot.required_skills = ["python"]
        return agg


class FakeArtifactService:
    async def generate_match(self, application_id, cv_language):
        return MatchView(
            id=uuid_mod.uuid4(),
            overall_score=0.7,
            semantic_score=0.7,
            skill_score=0.7,
            experience_score=0.7,
            language_score=0.7,
            matched_skills=["python"],
            missing_skills=["k8s"],
            pros=[],
            cons=[],
            recommendations=[],
            cv_language=cv_language,
            created_at=datetime.now(timezone.utc),
        )

    async def generate_optimization(self, application_id, cv_language, match_id):
        raise ValidationError("No match found")

    async def generate_interview_prep(self, application_id):
        return InterviewPrepView(
            id=uuid_mod.uuid4(),
            competencies_to_probe=["leadership"],
            technical_topics=["k8s"],
            negotiation_points=["remote"],
            matched_stories=[],
            created_at=datetime.now(timezone.utc),
        )


@pytest.fixture()
def application_service() -> FakeApplicationService:
    return FakeApplicationService()


@pytest.fixture()
def artifact_service() -> FakeArtifactService:
    return FakeArtifactService()


@pytest.fixture()
def client(
    application_service: FakeApplicationService, artifact_service: FakeArtifactService
) -> TestClient:
    app = FastAPI()
    register_domain_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: True
    app.dependency_overrides[get_application_service] = lambda: application_service
    app.dependency_overrides[get_artifact_service] = lambda: artifact_service
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: FakeOrchestrator()
    return TestClient(app)


def test_create_manual_application_returns_aggregate(client: TestClient):
    resp = client.post(
        "/applications",
        json={"title": "SRE", "company": "Acme", "description": "Run k8s"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "SRE"
    assert body["job_snapshot"]["description"] == "Run k8s"


def test_create_manual_application_returns_pipeline_metadata(client: TestClient):
    resp = client.post(
        "/applications",
        json={
            "title": "SRE",
            "company": "Acme",
            "description": "Run k8s",
            "location": "Quito",
            "remote_modality": "onsite",
            "salary_range": "USD 1,500-2,000/mo",
            "source": "Referral",
            "posted_date": "2026-07-01T00:00:00Z",
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["location"] == "Quito"
    assert body["remote_modality"] == "on_site"
    assert body["salary_range"] == "USD 1,500-2,000/mo"
    assert body["source"] == "Referral"


def test_create_rejects_missing_description(client: TestClient):
    resp = client.post("/applications", json={"title": "SRE", "company": "Acme"})
    assert resp.status_code == 422


def test_list_returns_artifact_flags(client: TestClient):
    client.post("/applications", json={"title": "X", "company": "Y", "description": "Z"})
    resp = client.get("/applications")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert {"has_match", "has_optimization", "has_prep", "latest_match_score"} <= row.keys()
    # Pipeline-view enrichment fields folded in from the former Tracking page.
    assert {
        "job_id",
        "location",
        "remote_modality",
        "salary_range",
        "source",
        "posted_date",
    } <= row.keys()
    assert row["has_match"] is False


def test_list_manual_application_uses_persisted_metadata(client: TestClient):
    client.post(
        "/applications",
        json={
            "title": "SRE",
            "company": "Acme",
            "description": "Run k8s",
            "location": "Quito",
            "remote_modality": "remote",
            "salary_range": "USD 1,500-2,000/mo",
            "source": "Referral",
            "posted_date": "2026-07-01T00:00:00Z",
        },
    )

    row = client.get("/applications").json()[0]

    assert row["location"] == "Quito"
    assert row["remote_modality"] == "remote"
    assert row["salary_range"] == "USD 1,500-2,000/mo"
    assert row["source"] == "Referral"


def test_list_prefers_live_ingested_metadata_with_field_fallback(
    client: TestClient, application_service
):
    job_id = uuid_mod.uuid4()
    aggregate = _make_aggregate(
        job_id=job_id,
        location="Fallback location",
        remote_modality="hybrid",
        salary_range="USD 1,500/mo",
        source="Fallback source",
        posted_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    application_service._store[aggregate.id] = aggregate
    FakeOrchestrator.jobs_by_id[str(job_id)] = SimpleNamespace(
        location="Live location",
        remote_modality=None,
        salary_range="USD 2,000/mo",
        source="Live source",
        posted_date=None,
    )

    try:
        row = client.get("/applications").json()[0]
    finally:
        FakeOrchestrator.jobs_by_id.clear()

    assert row["location"] == "Live location"
    assert row["remote_modality"] == "hybrid"
    assert row["salary_range"] == "USD 2,000/mo"
    assert row["source"] == "Live source"
    assert row["posted_date"].startswith("2026-06-01")


def test_list_paginates_and_reports_total(client: TestClient):
    for i in range(3):
        client.post("/applications", json={"title": f"T{i}", "company": "Y", "description": "Z"})
    resp = client.get("/applications", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.headers["X-Total-Count"] == "3"

    page2 = client.get("/applications", params={"limit": 2, "offset": 2})
    assert len(page2.json()) == 1
    assert page2.headers["X-Total-Count"] == "3"


def test_list_rejects_invalid_pagination(client: TestClient):
    assert client.get("/applications", params={"limit": 0}).status_code == 422
    assert client.get("/applications", params={"offset": -1}).status_code == 422


def test_get_returns_aggregate(client: TestClient):
    resp = client.post("/applications", json={"title": "X", "company": "Y", "description": "Z"})
    app_id = resp.json()["id"]
    resp = client.get(f"/applications/{app_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == app_id


def test_get_missing_returns_404(client: TestClient):
    resp = client.get(f"/applications/{uuid_mod.uuid4()}")
    assert resp.status_code == 404


def test_update_snapshot(client: TestClient):
    resp = client.post("/applications", json={"title": "X", "company": "Y", "description": "old"})
    app_id = resp.json()["id"]
    resp = client.put(
        f"/applications/{app_id}/job-snapshot",
        json={"description": "new", "required_skills": ["python"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job_snapshot"]["description"] == "new"
    assert body["job_snapshot"]["required_skills"] == ["python"]


def test_regenerate_skills(client: TestClient):
    resp = client.post("/applications", json={"title": "X", "company": "Y", "description": "desc"})
    app_id = resp.json()["id"]
    resp = client.post(f"/applications/{app_id}/job-snapshot/regenerate-skills")
    assert resp.status_code == 200, resp.text
    assert resp.json()["job_snapshot"]["required_skills"] == ["python"]


def test_delete(client: TestClient):
    resp = client.post("/applications", json={"title": "X", "company": "Y", "description": "Z"})
    app_id = resp.json()["id"]
    resp = client.delete(f"/applications/{app_id}")
    assert resp.status_code == 204
    resp = client.get(f"/applications/{app_id}")
    assert resp.status_code == 404


def test_create_with_unknown_job_id_returns_404(client: TestClient):
    resp = client.post(
        "/applications",
        json={"job_id": str(uuid_mod.uuid4())},
    )
    assert resp.status_code == 404


def test_create_with_already_tracked_job_returns_409(
    client: TestClient, application_service: FakeApplicationService
):
    """A ConflictError from the service maps to 409 via the shared handler
    (type-based), not by matching an 'already tracked' substring."""

    async def _raise_conflict(job_id):
        raise ConflictError("This job is already tracked")

    application_service.create_from_ingested = _raise_conflict  # type: ignore[assignment]

    resp = client.post("/applications", json={"job_id": str(uuid_mod.uuid4())})

    assert resp.status_code == 409
    assert resp.json()["detail"] == "This job is already tracked"


class FakeApplyService:
    """mark_applied either succeeds silently or raises the scripted error."""

    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc
        self.calls: list[uuid_mod.UUID] = []

    async def mark_applied(self, application_id):
        self.calls.append(application_id)
        if self.exc is not None:
            raise self.exc


def _client_with_apply(
    application_service: FakeApplicationService, apply_service: FakeApplyService
) -> TestClient:
    app = FastAPI()
    register_domain_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: True
    app.dependency_overrides[get_application_service] = lambda: application_service
    app.dependency_overrides[get_apply_service] = lambda: apply_service
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: FakeOrchestrator()
    return TestClient(app)


def test_mark_applied_returns_aggregate(application_service: FakeApplicationService):
    client = _client_with_apply(application_service, FakeApplyService())
    resp = client.post("/applications", json={"title": "X", "company": "Y", "description": "Z"})
    app_id = resp.json()["id"]

    resp = client.post(f"/applications/{app_id}/mark-applied")

    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == app_id


def test_mark_applied_on_terminal_application_returns_409(
    application_service: FakeApplicationService,
):
    """A terminal (accepted/rejected) application cannot transition to APPLIED:
    the state-machine rejection is a 409 conflict, not a 404 (issue found in
    the #195 review — this was the third update_status call site)."""
    apply_service = FakeApplyService(
        exc=InvalidStatusTransitionError("Cannot change status of a rejected application")
    )
    client = _client_with_apply(application_service, apply_service)
    resp = client.post("/applications", json={"title": "X", "company": "Y", "description": "Z"})
    app_id = resp.json()["id"]

    resp = client.post(f"/applications/{app_id}/mark-applied")

    assert resp.status_code == 409
    assert "rejected" in resp.json()["detail"]


def test_mark_applied_missing_application_returns_404(
    application_service: FakeApplicationService,
):
    apply_service = FakeApplyService(exc=ValueError("Application not found"))
    client = _client_with_apply(application_service, apply_service)

    resp = client.post(f"/applications/{uuid_mod.uuid4()}/mark-applied")

    assert resp.status_code == 404


def test_generate_match(client: TestClient):
    resp = client.post("/applications", json={"title": "X", "company": "Y", "description": "Z"})
    app_id = resp.json()["id"]
    resp = client.post(f"/applications/{app_id}/match", json={"cv_language": "en"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["overall_score"] == 0.7


def test_generate_optimization_without_match_returns_400(client: TestClient):
    resp = client.post("/applications", json={"title": "X", "company": "Y", "description": "Z"})
    app_id = resp.json()["id"]
    resp = client.post(f"/applications/{app_id}/optimize", json={"cv_language": "en"})
    assert resp.status_code == 400


def test_generate_interview_prep(client: TestClient):
    resp = client.post("/applications", json={"title": "X", "company": "Y", "description": "Z"})
    app_id = resp.json()["id"]
    resp = client.post(f"/applications/{app_id}/interview-prep")
    assert resp.status_code == 201, resp.text
    assert resp.json()["competencies_to_probe"] == ["leadership"]


def test_artifact_routes_are_rate_limited_when_hammered(
    application_service: FakeApplicationService, artifact_service: FakeArtifactService
):
    """The four LLM artifact routes (match/optimize/interview-prep/cover-letter)
    share the same expensive-operation limiter as optimization/matching."""
    app = FastAPI()
    register_domain_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: True
    app.dependency_overrides[get_application_service] = lambda: application_service
    app.dependency_overrides[get_artifact_service] = lambda: artifact_service
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: FakeOrchestrator()
    app.state.rate_limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    limited_client = TestClient(app)

    resp = limited_client.post(
        "/applications", json={"title": "X", "company": "Y", "description": "Z"}
    )
    app_id = resp.json()["id"]

    first = limited_client.post(f"/applications/{app_id}/match", json={"cv_language": "en"})
    assert first.status_code == 201, first.text

    second = limited_client.post(f"/applications/{app_id}/match", json={"cv_language": "en"})
    assert second.status_code == 429
    assert "Retry-After" in second.headers

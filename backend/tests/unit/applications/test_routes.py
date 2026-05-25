from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.applications.api.dependencies import (
    get_application_service,
    get_artifact_service,
)
from hiresense.applications.api.routes import router
from hiresense.applications.domain.aggregate import (
    ApplicationAggregate,
    CvOptimizationView,
    InterviewPrepView,
    JobSnapshotView,
    MatchView,
)
from hiresense.identity.api.dependencies import require_auth


def _make_aggregate(
    *,
    title: str = "Software Engineer",
    company: str = "Fieldguide",
    description: str = "job desc",
    required_skills: list[str] | None = None,
    match_count: int = 0,
    latest_match_score: float | None = None,
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
        job_id=None,
        title=title,
        company=company,
        url=None,
        status="saved",
        notes=None,
        applied_at=None,
        created_at=now,
        updated_at=now,
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

    async def create_from_manual(self, title, company, description, url, notes=None):
        agg = _make_aggregate(title=title, company=company, description=description)
        self._store[agg.id] = agg
        return agg

    async def create_from_ingested(self, job_id):
        raise ValueError(f"Job {job_id} not found")

    def get(self, application_id):
        agg = self._store.get(application_id)
        if agg is None:
            raise ValueError(f"Application {application_id} not found")
        return agg

    def list(self, status=None):
        return list(self._store.values())

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
        raise ValueError("No match found")

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
def client(application_service: FakeApplicationService, artifact_service: FakeArtifactService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: True
    app.dependency_overrides[get_application_service] = lambda: application_service
    app.dependency_overrides[get_artifact_service] = lambda: artifact_service
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
    assert row["has_match"] is False


def test_get_returns_aggregate(client: TestClient):
    resp = client.post(
        "/applications", json={"title": "X", "company": "Y", "description": "Z"}
    )
    app_id = resp.json()["id"]
    resp = client.get(f"/applications/{app_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == app_id


def test_get_missing_returns_404(client: TestClient):
    resp = client.get(f"/applications/{uuid_mod.uuid4()}")
    assert resp.status_code == 404


def test_update_snapshot(client: TestClient):
    resp = client.post(
        "/applications", json={"title": "X", "company": "Y", "description": "old"}
    )
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
    resp = client.post(
        "/applications", json={"title": "X", "company": "Y", "description": "desc"}
    )
    app_id = resp.json()["id"]
    resp = client.post(f"/applications/{app_id}/job-snapshot/regenerate-skills")
    assert resp.status_code == 200, resp.text
    assert resp.json()["job_snapshot"]["required_skills"] == ["python"]


def test_delete(client: TestClient):
    resp = client.post(
        "/applications", json={"title": "X", "company": "Y", "description": "Z"}
    )
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


def test_generate_match(client: TestClient):
    resp = client.post(
        "/applications", json={"title": "X", "company": "Y", "description": "Z"}
    )
    app_id = resp.json()["id"]
    resp = client.post(f"/applications/{app_id}/match", json={"cv_language": "en"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["overall_score"] == 0.7


def test_generate_optimization_without_match_returns_400(client: TestClient):
    resp = client.post(
        "/applications", json={"title": "X", "company": "Y", "description": "Z"}
    )
    app_id = resp.json()["id"]
    resp = client.post(f"/applications/{app_id}/optimize", json={"cv_language": "en"})
    assert resp.status_code == 400


def test_generate_interview_prep(client: TestClient):
    resp = client.post(
        "/applications", json={"title": "X", "company": "Y", "description": "Z"}
    )
    app_id = resp.json()["id"]
    resp = client.post(f"/applications/{app_id}/interview-prep")
    assert resp.status_code == 201, resp.text
    assert resp.json()["competencies_to_probe"] == ["leadership"]

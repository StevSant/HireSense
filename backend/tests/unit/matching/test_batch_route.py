from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.matching.api.dependencies import (
    get_batch_evaluation_service,
    get_ingestion_orchestrator_for_matching,
    get_tracking_service_for_matching,
)
from hiresense.matching.api.routes import router
from hiresense.matching.domain.batch_service import BatchResult
from hiresense.matching.domain.scorers.base import DimensionResult


class FakeBatchService:
    async def evaluate_batch(self, jobs):
        return [
            BatchResult(
                job_title=j.get("title", ""),
                company=j.get("company", ""),
                source=j.get("source", "unknown"),
                source_id=j.get("source_id", ""),
                composite_score=0.8,
                dimensions=[
                    DimensionResult(
                        dimension="seniority_fit", score=0.8, rationale="Good", weight=10
                    ),
                ],
            )
            for j in jobs
        ]


class FakeTrackedApp:
    def __init__(self, id, title, company, url=None):
        self.id = id
        self.title = title
        self.company = company
        self.url = url


class FakeTrackingService:
    def __init__(self):
        self._apps = [
            FakeTrackedApp(id=uuid.uuid4(), title="SWE", company="Acme"),
            FakeTrackedApp(id=uuid.uuid4(), title="ML Eng", company="Beta"),
        ]

    def list(self, status=None):
        return self._apps

    def get(self, id):
        for a in self._apps:
            if a.id == id:
                return a
        raise ValueError(f"Not found: {id}")


class FakeNormalizedJob:
    def __init__(self, id, title, company, description="", skills=None, location=""):
        self.id = id
        self.title = title
        self.company = company
        self.description = description
        self.skills = skills or []
        self.location = location


class FakeIngestionOrchestrator:
    def list_jobs(self):
        return [FakeNormalizedJob(id="ing-1", title="Data Eng", company="Gamma")]


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_batch_evaluation_service] = lambda: FakeBatchService()
    app.dependency_overrides[get_tracking_service_for_matching] = lambda: FakeTrackingService()
    app.dependency_overrides[get_ingestion_orchestrator_for_matching] = lambda: (
        FakeIngestionOrchestrator()
    )
    return app


def test_batch_evaluate_all_tracked() -> None:
    client = TestClient(_make_app())
    response = client.post("/matching/batch-evaluate", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["source"] == "tracked"


def test_batch_evaluate_specific_ids() -> None:
    tracking_svc = FakeTrackingService()
    app_id = str(tracking_svc._apps[0].id)
    app = _make_app()
    app.dependency_overrides[get_tracking_service_for_matching] = lambda: tracking_svc
    client = TestClient(app)
    response = client.post("/matching/batch-evaluate", json={"tracked_app_ids": [app_id]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 1


def test_batch_evaluate_with_ingested() -> None:
    client = TestClient(_make_app())
    response = client.post("/matching/batch-evaluate", json={"include_ingested": True})
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 3
    sources = {r["source"] for r in data["results"]}
    assert "tracked" in sources
    assert "ingested" in sources


def test_batch_evaluate_empty_pipeline() -> None:
    class EmptyTrackingService:
        def list(self, status=None):
            return []

        def get(self, id):
            raise ValueError("Not found")

    app = _make_app()
    app.dependency_overrides[get_tracking_service_for_matching] = lambda: EmptyTrackingService()
    client = TestClient(app)
    response = client.post("/matching/batch-evaluate", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 0
    assert data["results"] == []


def test_batch_evaluate_skips_missing_tracked_ids() -> None:
    client = TestClient(_make_app())
    fake_id = str(uuid.uuid4())
    response = client.post("/matching/batch-evaluate", json={"tracked_app_ids": [fake_id]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 0

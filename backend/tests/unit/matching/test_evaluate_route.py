from fastapi import FastAPI
from fastapi.testclient import TestClient
from hiresense.identity.api.dependencies import require_auth
from hiresense.matching.api.dependencies import get_matching_orchestrator
from hiresense.matching.api.routes import router
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.services import EvaluationResult


class FakeOrchestrator:
    async def evaluate(self, job, profile=None, dimension_scorers=None):
        return EvaluationResult(
            composite_score=0.75,
            job_title=job.get("title", "Unknown"),
            company=job.get("company", "Unknown"),
            dimensions=[
                DimensionResult(dimension="seniority_fit", score=0.8, rationale="Good fit", weight=10),
                DimensionResult(dimension="compensation", score=0.7, rationale="Competitive", weight=10),
            ],
        )

    async def analyze(self, **kwargs): pass


def _make_app():
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    app.dependency_overrides[get_matching_orchestrator] = lambda: FakeOrchestrator()
    return app


def test_evaluate_endpoint_returns_result():
    client = TestClient(_make_app())
    response = client.post("/matching/evaluate", json={"job_title": "Backend Engineer", "company": "Anthropic", "description": "Build APIs"})
    assert response.status_code == 200
    data = response.json()
    assert data["composite_score"] == 0.75
    assert len(data["dimensions"]) == 2


def test_evaluate_endpoint_empty_request():
    client = TestClient(_make_app())
    response = client.post("/matching/evaluate", json={})
    assert response.status_code == 200


def test_evaluate_endpoint_with_job_id():
    client = TestClient(_make_app())
    response = client.post("/matching/evaluate", json={"job_id": "some-uuid"})
    assert response.status_code == 200

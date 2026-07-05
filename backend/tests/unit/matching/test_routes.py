import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from hiresense.identity.api.dependencies import require_auth
from hiresense.matching.api.routes import get_matching_orchestrator, router
from hiresense.matching.domain.models import MatchResult, ScoreBreakdown


class FakeMatchingOrchestrator:
    async def analyze(self, **kwargs) -> MatchResult:
        return MatchResult(
            id="match-1",
            job_id=kwargs.get("job_id", "job-1"),
            cv_id=kwargs.get("cv_id", "cv-1"),
            overall_score=0.78,
            breakdown=ScoreBreakdown(
                semantic_score=0.85,
                skill_score=0.70,
                experience_score=0.60,
                language_score=1.0,
            ),
            matched_skills=["python", "fastapi"],
            missing_skills=["kubernetes"],
            pros=["Strong Python experience"],
            cons=["No K8s experience"],
            recommendations=["Learn Kubernetes"],
        )


@pytest.mark.asyncio
async def test_analyze_endpoint() -> None:
    app = FastAPI()
    fake = FakeMatchingOrchestrator()
    app.dependency_overrides[get_matching_orchestrator] = lambda: fake
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/matching/analyze",
            json={
                "job_id": "job-1",
                "cv_id": "cv-1",
                "job_description": "Backend engineer needed",
                "job_skills": ["python", "fastapi", "kubernetes"],
                "cv_summary": "Python developer",
                "cv_skills": ["python", "fastapi", "django"],
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_score"] == 0.78
    assert "python" in data["matched_skills"]
    assert "kubernetes" in data["missing_skills"]
    assert len(data["pros"]) > 0


@pytest.mark.asyncio
async def test_requires_auth_without_token() -> None:
    """Router-level auth: requests with no bearer token are rejected."""
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/matching/analyze")
    assert resp.status_code == 401

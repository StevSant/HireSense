import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from hiresense.identity.api.dependencies import require_auth
from hiresense.optimization.api.routes import get_cv_optimizer, router
from hiresense.optimization.domain import OptimizationError
from hiresense.optimization.domain.models import OptimizationResult, SectionChange


class FakeCVOptimizer:
    async def optimize(self, **kwargs) -> OptimizationResult:
        return OptimizationResult(
            id="opt-1",
            match_id=kwargs.get("match_id", "match-1"),
            job_id=kwargs.get("job_id", "job-1"),
            cv_id=kwargs.get("cv_id", "cv-1"),
            changes=[
                SectionChange(
                    section_name="SUMMARY",
                    original="Old summary",
                    optimized="New summary",
                    reason="Better alignment",
                )
            ],
            original_tex="\\section*{SUMMARY}\nOld summary",
            optimized_tex="\\section*{SUMMARY}\nNew summary",
            improvement_summary="Improved summary section",
        )


@pytest.mark.asyncio
async def test_optimize_endpoint() -> None:
    app = FastAPI()
    fake = FakeCVOptimizer()
    app.dependency_overrides[get_cv_optimizer] = lambda: fake
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/optimization/optimize",
            json={
                "match_id": "match-1",
                "job_id": "job-1",
                "cv_id": "cv-1",
                "original_tex": "\\section*{SUMMARY}\nOld summary",
                "job_description": "Backend engineer needed",
                "job_skills": ["python", "fastapi"],
                "missing_skills": ["kubernetes"],
                "recommendations": ["Highlight API experience"],
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "opt-1"
    assert len(data["changes"]) == 1
    assert data["changes"][0]["section_name"] == "SUMMARY"
    assert data["improvement_summary"] == "Improved summary section"
    assert data["optimized_tex"] != data["original_tex"]
    assert data["claim_readiness"] == {
        "ready": True,
        "supported_changes": [],
        "blocked_changes": [],
        "supported_evidence": [],
    }


@pytest.mark.asyncio
async def test_optimize_endpoint_returns_503_on_optimization_error() -> None:
    # A failing optimizer must surface as a clean 503 (via the app-level handler
    # registered in create_app), never a 200 with the unoptimized CV (#142).
    class FailingCVOptimizer:
        async def optimize(self, **kwargs) -> OptimizationResult:
            raise OptimizationError("CV optimization failed")

    app = FastAPI()

    @app.exception_handler(OptimizationError)
    async def _handler(_request, _exc) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "CV optimization failed"})

    app.dependency_overrides[get_cv_optimizer] = lambda: FailingCVOptimizer()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/optimization/optimize",
            json={
                "match_id": "match-1",
                "job_id": "job-1",
                "cv_id": "cv-1",
                "original_tex": "\\section*{SUMMARY}\nOld summary",
                "job_description": "Backend engineer needed",
                "job_skills": ["python"],
            },
        )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_requires_auth_without_token() -> None:
    """Router-level auth: requests with no bearer token are rejected."""
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/optimization/optimize")
    assert resp.status_code == 401

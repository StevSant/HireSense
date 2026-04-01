import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from hiresense.optimization.api.routes import get_cv_optimizer, router
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
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
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

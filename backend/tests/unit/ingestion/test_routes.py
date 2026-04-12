import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from hiresense.ingestion.api import get_ingestion_orchestrator, router
from hiresense.ingestion.domain.models import NormalizedJob


class FakeOrchestrator:
    def __init__(self) -> None:
        self.called = False

    async def run(self, filters=None) -> list[NormalizedJob]:
        self.called = True
        return [
            NormalizedJob(
                id="test-1",
                title="Engineer",
                company="Co",
                description="Do things",
                skills=["python"],
                location="Remote",
                source="remotive",
                source_type="api",
                language="en",
                url="https://example.com/1",
            )
        ]


@pytest.mark.asyncio
async def test_fetch_jobs_endpoint() -> None:
    app = FastAPI()
    fake = FakeOrchestrator()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: fake
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/fetch")

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["jobs"][0]["title"] == "Engineer"
    assert fake.called

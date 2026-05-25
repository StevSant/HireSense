import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from hiresense.ingestion.api import get_ingestion_orchestrator, get_portal_scanner, router
from hiresense.ingestion.domain.models import NormalizedJob


BOARD_JOB = NormalizedJob(
    id="board-1",
    title="Board Engineer",
    company="Co",
    description="Board job",
    skills=["python"],
    location="Remote",
    source="remotive",
    source_type="api",
    language="en",
    url="https://example.com/board",
)

PORTAL_JOB = NormalizedJob(
    id="portal-1",
    title="Portal Engineer",
    company="PortalCo",
    description="Portal job",
    skills=["go"],
    location="NYC",
    source="PortalCo",
    source_type="api",
    platform="greenhouse",
    categories=["ai-research"],
    language="en",
    url="https://example.com/portal",
)


class FakeOrchestrator:
    def __init__(self) -> None:
        self.called = False

    async def run(self, filters=None) -> list[NormalizedJob]:
        self.called = True
        return [BOARD_JOB]

    def list_jobs(self) -> list[NormalizedJob]:
        return [BOARD_JOB]


class FakeScanner:
    def list_jobs(self) -> list[NormalizedJob]:
        return [PORTAL_JOB]


def _make_app() -> tuple[FastAPI, FakeOrchestrator, FakeScanner]:
    app = FastAPI()
    orch = FakeOrchestrator()
    scanner = FakeScanner()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: orch
    app.dependency_overrides[get_portal_scanner] = lambda: scanner
    app.include_router(router)
    return app, orch, scanner


@pytest.mark.asyncio
async def test_list_jobs_boards_tab() -> None:
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs?tab=boards")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["jobs"][0]["source"] == "remotive"
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_list_jobs_portals_tab() -> None:
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs?tab=portals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["jobs"][0]["source"] == "PortalCo"


@pytest.mark.asyncio
async def test_list_jobs_pagination() -> None:
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs?tab=boards&page=1&page_size=20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_list_jobs_filter_by_source() -> None:
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs?tab=boards&source=nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_fetch_jobs_endpoint() -> None:
    app, fake_orch, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/fetch")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert fake_orch.called


@pytest.mark.asyncio
async def test_list_jobs_strict_location_filters_non_matching() -> None:
    chile_job = NormalizedJob(
        id="job-chile",
        title="Chile Engineer",
        company="Co",
        description="Job",
        skills=[],
        location="Chile (Remote)",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/chile",
    )
    restricted_job = NormalizedJob(
        id="job-restricted",
        title="USA Only Engineer",
        company="Co",
        description="Job",
        skills=[],
        location="USA only",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/usa",
    )
    ambiguous_remote_job = NormalizedJob(
        id="job-remote-remote",
        title="Remote Remote Engineer",
        company="Co",
        description="Job",
        skills=[],
        location="Remote (Remote)",
        source="getonboard",
        source_type="api",
        language="en",
        url="https://example.com/getonboard",
    )
    worldwide_job = NormalizedJob(
        id="job-worldwide",
        title="Global Engineer",
        company="Co",
        description="Job",
        skills=[],
        location="Worldwide",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/global",
    )

    class MultiJobOrchestrator:
        async def run(self, filters=None) -> list[NormalizedJob]:
            return []

        def list_jobs(self) -> list[NormalizedJob]:
            return [chile_job, restricted_job, ambiguous_remote_job, worldwide_job]

    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: MultiJobOrchestrator()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/ingestion/jobs",
            params={"tab": "boards", "user_location": "Chile", "strict_location": "true"},
        )

    assert resp.status_code == 200
    data = resp.json()
    returned_ids = {j["id"] for j in data["jobs"]}
    assert returned_ids == {"job-chile", "job-worldwide"}

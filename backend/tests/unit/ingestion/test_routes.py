import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from hiresense.ingestion.api import get_ingestion_orchestrator, get_portal_scanner, router
from hiresense.ingestion.api.dependencies import get_semantic_scoring
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.profile.api.dependencies import get_profile_service


class FakeProfileService:
    async def list_profiles(self):
        return []


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

    def persist_scores(self, job_id, match_score, semantic_score) -> None:
        pass


class FakeScanner:
    def list_jobs(self) -> list[NormalizedJob]:
        return [PORTAL_JOB]

    def get_job_by_id(self, job_id):
        return None

    def persist_scores(self, job_id, match_score, semantic_score) -> None:
        pass


def _make_app() -> tuple[FastAPI, FakeOrchestrator, FakeScanner]:
    app = FastAPI()
    orch = FakeOrchestrator()
    scanner = FakeScanner()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: orch
    app.dependency_overrides[get_portal_scanner] = lambda: scanner
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
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

        def persist_scores(self, job_id, match_score, semantic_score) -> None:
            pass

    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: MultiJobOrchestrator()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/ingestion/jobs",
            params={"tab": "boards", "user_location": "Chile", "strict_location": "true"},
        )

    assert resp.status_code == 200
    data = resp.json()
    returned_ids = {j["id"] for j in data["jobs"]}
    # Ambiguous "Remote (Remote)" jobs now pass through — fully-remote
    # postings are treated as applyable from anywhere.
    assert returned_ids == {"job-chile", "job-worldwide", "job-remote-remote"}


# ---------------------------------------------------------------------------
# Work Unit E1 — get_pre_ranker dependency returns None on a bare app
# (no app.state.ingestion wired)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pre_ranker_returns_none_on_bare_app() -> None:
    """get_pre_ranker must return None defensively when app has no ingestion state."""
    from fastapi import FastAPI, Request
    from hiresense.ingestion.api.dependencies import get_pre_ranker

    bare_app = FastAPI()

    @bare_app.get("/test-pre-ranker")
    async def _probe(request: Request):
        result = get_pre_ranker(request)
        return {"is_none": result is None}

    async with AsyncClient(transport=ASGITransport(app=bare_app), base_url="http://test") as client:
        resp = await client.get("/test-pre-ranker")
    assert resp.status_code == 200
    assert resp.json()["is_none"] is True


@pytest.mark.asyncio
async def test_get_pre_ranker_returns_instance_when_provider_has_it() -> None:
    """get_pre_ranker returns the SemanticPreRanker when wired on app state."""
    from fastapi import FastAPI, Request
    from hiresense.ingestion.api.dependencies import get_pre_ranker
    from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker

    fake_ranker = SemanticPreRanker(None, None, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

    class FakeProvider:
        def get_pre_ranker(self):
            return fake_ranker

    wired_app = FastAPI()
    wired_app.state.ingestion = FakeProvider()

    @wired_app.get("/test-pre-ranker")
    async def _probe(request: Request):
        result = get_pre_ranker(request)
        return {"is_none": result is None}

    async with AsyncClient(transport=ASGITransport(app=wired_app), base_url="http://test") as client:
        resp = await client.get("/test-pre-ranker")
    assert resp.status_code == 200
    assert resp.json()["is_none"] is False

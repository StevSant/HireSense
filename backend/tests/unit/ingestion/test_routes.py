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

    def persist_scores_batch(self, updates) -> None:
        pass


class FakeScanner:
    def list_jobs(self) -> list[NormalizedJob]:
        return [PORTAL_JOB]

    def get_job_by_id(self, job_id):
        return None

    def persist_scores(self, job_id, match_score, semantic_score) -> None:
        pass

    def persist_scores_batch(self, updates) -> None:
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
async def test_list_jobs_accepts_title_asc_sort() -> None:
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs", params={"tab": "boards", "sort": "title_asc"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_jobs_invalid_sort_falls_back_to_default() -> None:
    # An unknown token must not 422; it falls back to match_desc and returns 200.
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs", params={"tab": "boards", "sort": "bogus_xyz"})
    assert resp.status_code == 200


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

        def persist_scores_batch(self, updates) -> None:
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


@pytest.mark.asyncio
async def test_revalidate_endpoint_returns_closed_count() -> None:
    from hiresense.ingestion.api.dependencies import get_revalidation_service

    class FakeRevalidation:
        async def sweep(self):
            return ["x", "y", "z"]

    app = FastAPI()
    app.dependency_overrides[get_revalidation_service] = lambda: FakeRevalidation()
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/revalidate")

    assert resp.status_code == 200
    assert resp.json() == {"closed": 3}


@pytest.mark.asyncio
async def test_revalidate_endpoint_503_when_unconfigured() -> None:
    app = FastAPI()  # no override -> dependency returns None (no app.state.ingestion)
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/revalidate")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_pre_ranker_promotes_job_to_page_one_before_pagination() -> None:
    """#18 fix: global pre-rank runs BEFORE pagination, so a job the ANN ranks
    best reaches page 1 even if it was last in insertion order — and with no
    explicit sort param (default match_desc)."""
    from hiresense.ingestion.api.dependencies import get_pre_ranker

    jobs = [
        NormalizedJob(id=f"job-{i}", title=f"T{i}", company="Co", description="d",
                      source="remotive", source_type="api", language="en",
                      url=f"https://e.com/{i}")
        for i in range(3)
    ]

    class _Orch:
        async def run(self, filters=None): return []
        def list_jobs(self): return list(jobs)
        def persist_scores(self, *a): pass
        def persist_scores_batch(self, updates): pass

    class _PreRanker:
        # Simulate ANN deciding job-2 is the best match (was last in order).
        async def rerank(self, corpus, skill_by_id, skills, summary, bucket):
            by_id = {j.id: j for j in corpus}
            return [by_id["job-2"], by_id["job-0"], by_id["job-1"]]

    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: _Orch()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    app.dependency_overrides[get_pre_ranker] = lambda: _PreRanker()
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # page_size=1, no `sort` param -> default match_desc, pre-rank decides page 1
        resp = await client.get("/ingestion/jobs", params={"tab": "boards", "page_size": 1, "min_score": 0})

    assert resp.status_code == 200
    body = resp.json()
    assert body["jobs"][0]["id"] == "job-2"  # pre-ranked to the top, reached page 1


# ---------------------------------------------------------------------------
# #76 — sort-only fast path: rescore=false skips the global ANN re-rank and the
# full-corpus persist write (scores are already persisted; a reorder is cheap).
# ---------------------------------------------------------------------------


class _Section:
    content = "experienced python engineer"


class _Profile:
    skills = ["python"]
    sections = [_Section()]


class FakeProfileWithSkills:
    async def list_profiles(self):
        return [_Profile()]


def _scored_jobs() -> list[NormalizedJob]:
    """Three board jobs carrying *persisted* match scores (semantic still None)."""
    scores = {"job-0": 0.3, "job-1": 0.9, "job-2": 0.6}
    return [
        NormalizedJob(
            id=jid, title=f"T{jid}", company="Co", description="d", skills=["python"],
            source="remotive", source_type="api", language="en",
            url=f"https://e.com/{jid}", match_score=score,
        )
        for jid, score in scores.items()
    ]


class _RecordingPreRanker:
    def __init__(self) -> None:
        self.called = False

    async def rerank(self, corpus, skill_by_id, skills, summary, bucket):
        self.called = True
        # If it ran, it would flip the order — used to prove it did NOT run.
        return list(reversed(corpus))


def _make_scored_app(pre_ranker, persisted: list):
    from hiresense.ingestion.api.dependencies import get_pre_ranker

    jobs = _scored_jobs()

    class _Orch:
        async def run(self, filters=None):
            return []

        def list_jobs(self):
            return list(jobs)

        def persist_scores(self, *a):
            pass

        def persist_scores_batch(self, updates):
            persisted.append(updates)

    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: _Orch()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileWithSkills()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    app.dependency_overrides[get_pre_ranker] = lambda: pre_ranker
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_rescore_false_skips_pre_rank_and_persist() -> None:
    pre = _RecordingPreRanker()
    persisted: list = []
    app = _make_scored_app(pre, persisted)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/ingestion/jobs",
            params={"tab": "boards", "rescore": "false", "min_score": 0},
        )

    assert resp.status_code == 200
    # The global ANN re-rank must not run on a sort-only request...
    assert pre.called is False
    # ...nor the full-corpus score persist write.
    assert persisted == []


@pytest.mark.asyncio
async def test_rescore_false_sorts_by_persisted_scores() -> None:
    pre = _RecordingPreRanker()
    persisted: list = []
    app = _make_scored_app(pre, persisted)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Default sort = match_desc; ordering must come from the persisted scores
        # (0.9, 0.6, 0.3), NOT from the pre-ranker's reversal.
        resp = await client.get(
            "/ingestion/jobs",
            params={"tab": "boards", "rescore": "false", "min_score": 0},
        )

    assert resp.status_code == 200
    ids = [j["id"] for j in resp.json()["jobs"]]
    assert ids == ["job-1", "job-2", "job-0"]


@pytest.mark.asyncio
async def test_rescore_default_still_runs_pre_rank_and_persist() -> None:
    # Regression: omitting `rescore` keeps the full pipeline (rescore defaults True).
    pre = _RecordingPreRanker()
    persisted: list = []
    app = _make_scored_app(pre, persisted)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs", params={"tab": "boards", "min_score": 0})

    assert resp.status_code == 200
    assert pre.called is True
    assert persisted != []

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from hiresense.identity.api.dependencies import require_auth
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

    def list_jobs(self, criteria=None) -> list[NormalizedJob]:
        return [BOARD_JOB]

    def persist_scores(self, job_id, match_score, semantic_score) -> None:
        pass

    def persist_scores_batch(self, updates) -> None:
        pass


class FakeScanner:
    def list_jobs(self, criteria=None) -> list[NormalizedJob]:
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
    app.dependency_overrides[require_auth] = lambda: "test-user"
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
async def test_fetch_jobs_triggers_revalidation_sweep_in_background() -> None:
    """A user-initiated fetch also kicks off the URL-probe sweep (after the
    response is sent) so dead listings get closed without the external cron."""
    from hiresense.ingestion.api.dependencies import get_revalidation_service

    class FakeRevalidation:
        def __init__(self) -> None:
            self.swept = 0

        async def sweep(self) -> list[str]:
            self.swept += 1
            return []

    app, _, _ = _make_app()
    reval = FakeRevalidation()
    app.dependency_overrides[get_revalidation_service] = lambda: reval

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/fetch")

    assert resp.status_code == 200
    # BackgroundTasks run after the response is delivered (within the ASGI call).
    assert reval.swept == 1


@pytest.mark.asyncio
async def test_fetch_jobs_without_revalidation_service_still_succeeds() -> None:
    # Bare app: get_revalidation_service resolves to None — fetch must not error.
    app, fake_orch, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/fetch")
    assert resp.status_code == 200
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
        # Explicit parenthetical geo-lock — the only thing the "jobs I can apply
        # to" filter hides for free-text sources now (a bare "USA only" passes).
        location="Remote (USA)",
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

        def list_jobs(self, criteria=None) -> list[NormalizedJob]:
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
    app.dependency_overrides[require_auth] = lambda: "test-user"
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

    fake_ranker = SemanticPreRanker(
        None, None, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6
    )

    class FakeProvider:
        def get_pre_ranker(self):
            return fake_ranker

    wired_app = FastAPI()
    wired_app.state.ingestion = FakeProvider()

    @wired_app.get("/test-pre-ranker")
    async def _probe(request: Request):
        result = get_pre_ranker(request)
        return {"is_none": result is None}

    async with AsyncClient(
        transport=ASGITransport(app=wired_app), base_url="http://test"
    ) as client:
        resp = await client.get("/test-pre-ranker")
    assert resp.status_code == 200
    assert resp.json()["is_none"] is False


@pytest.mark.asyncio
async def test_revalidate_endpoint_returns_closed_count() -> None:
    from hiresense.ingestion.api.dependencies import get_revalidation_service

    class FakeRevalidation:
        def __init__(self) -> None:
            self.swept = 0

        async def sweep(self):
            self.swept += 1
            return ["x", "y", "z"]

    app = FastAPI()
    reval = FakeRevalidation()
    app.dependency_overrides[get_revalidation_service] = lambda: reval
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/revalidate")

    assert resp.status_code == 200
    # Synchronous (cron) mode: waits and reports the closed ids.
    assert resp.json() == {"started": True, "closed": 3, "closed_ids": ["x", "y", "z"]}
    assert reval.swept == 1


@pytest.mark.asyncio
async def test_revalidate_endpoint_background_schedules_sweep() -> None:
    from hiresense.ingestion.api.dependencies import get_revalidation_service

    class FakeRevalidation:
        def __init__(self) -> None:
            self.swept = 0

        async def sweep(self):
            self.swept += 1
            return ["x", "y", "z"]

    app = FastAPI()
    reval = FakeRevalidation()
    app.dependency_overrides[get_revalidation_service] = lambda: reval
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/revalidate?background=true")

    assert resp.status_code == 200
    # Background mode returns immediately with no counts; the sweep still runs
    # (BackgroundTasks execute after the response within the ASGI call).
    assert resp.json() == {"started": True, "closed": 0, "closed_ids": []}
    assert reval.swept == 1


@pytest.mark.asyncio
async def test_revalidate_endpoint_with_job_ids_probes_now_and_schedules_sweep() -> None:
    from hiresense.ingestion.api.dependencies import get_revalidation_service

    class FakeRevalidation:
        def __init__(self) -> None:
            self.swept = 0
            self.probed_ids: list[str] | None = None

        async def revalidate_ids(self, job_ids):
            self.probed_ids = list(job_ids)
            return ["a"]  # one of the visible jobs was closed

        async def sweep(self):
            self.swept += 1
            return []

    app = FastAPI()
    reval = FakeRevalidation()
    app.dependency_overrides[get_revalidation_service] = lambda: reval
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/revalidate", json={"job_ids": ["a", "b", "c"]})

    assert resp.status_code == 200
    # Immediate result for the visible jobs...
    assert resp.json() == {"started": True, "closed": 1, "closed_ids": ["a"]}
    assert reval.probed_ids == ["a", "b", "c"]
    # ...plus a full background sweep for everything else.
    assert reval.swept == 1


@pytest.mark.asyncio
async def test_revalidate_endpoint_503_when_unconfigured() -> None:
    app = FastAPI()  # no override -> dependency returns None (no app.state.ingestion)
    app.dependency_overrides[require_auth] = lambda: "test-user"
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
        NormalizedJob(
            id=f"job-{i}",
            title=f"T{i}",
            company="Co",
            description="d",
            source="remotive",
            source_type="api",
            language="en",
            url=f"https://e.com/{i}",
        )
        for i in range(3)
    ]

    class _Orch:
        async def run(self, filters=None):
            return []

        def list_jobs(self, criteria=None):
            return list(jobs)

        def persist_scores(self, *a):
            pass

        def persist_scores_batch(self, updates):
            pass

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
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # page_size=1, no `sort` param -> default match_desc, pre-rank decides page 1
        resp = await client.get(
            "/ingestion/jobs", params={"tab": "boards", "page_size": 1, "min_score": 0}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["jobs"][0]["id"] == "job-2"  # pre-ranked to the top, reached page 1


# ---------------------------------------------------------------------------
# #76 — sort-only fast path: a pure reorder (rescore=false) must KEEP the full
# skill+ANN+min_score pipeline (so the result set/order is unchanged) but defer
# the blocking Tier-1 LLM call — quick scoring runs cache-only (llm_on_miss=False).
# ---------------------------------------------------------------------------


class _Section:
    content = "experienced python engineer"


class _Profile:
    skills = ["python"]
    sections = [_Section()]


class FakeProfileWithSkills:
    async def list_profiles(self):
        return [_Profile()]


class _RecordingPreRanker:
    def __init__(self) -> None:
        self.called = False

    async def rerank(self, corpus, skill_by_id, skills, summary, bucket):
        self.called = True
        return list(corpus)


class _RecordingQuickScoring:
    def __init__(self) -> None:
        self.llm_on_miss_calls: list[bool] = []

    async def score_page(self, jobs, skills, summary, *, llm_on_miss=True):
        self.llm_on_miss_calls.append(llm_on_miss)
        return {}


def _make_rescore_app(pre_ranker, quick_scoring):
    from hiresense.ingestion.api.dependencies import get_pre_ranker, get_quick_scoring

    jobs = [
        NormalizedJob(
            id=f"job-{i}",
            title=f"T{i}",
            company="Co",
            description="d",
            skills=["python"],
            source="remotive",
            source_type="api",
            language="en",
            url=f"https://e.com/{i}",
            match_score=0.5,
        )
        for i in range(3)
    ]

    class _Orch:
        async def run(self, filters=None):
            return []

        def list_jobs(self, criteria=None):
            return list(jobs)

        def persist_scores(self, *a):
            pass

        def persist_scores_batch(self, updates):
            pass

    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: _Orch()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileWithSkills()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    app.dependency_overrides[get_pre_ranker] = lambda: pre_ranker
    app.dependency_overrides[get_quick_scoring] = lambda: quick_scoring
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_rescore_false_defers_llm_but_keeps_pipeline() -> None:
    pre = _RecordingPreRanker()
    quick = _RecordingQuickScoring()
    app = _make_rescore_app(pre, quick)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/ingestion/jobs",
            params={"tab": "boards", "rescore": "false", "min_score": 0},
        )

    assert resp.status_code == 200
    # The scoring pipeline that determines the result set/order is preserved...
    assert pre.called is True
    # ...both score_page passes are cache-only on a pure reorder: the global
    # pre-pagination apply (always cache-only) and the page-level pass (deferred
    # because rescore=False). Neither fires the blocking LLM round-trip.
    assert quick.llm_on_miss_calls == [False, False]


@pytest.mark.asyncio
async def test_rescore_default_runs_llm_on_miss() -> None:
    # Omitting `rescore` (full load / filter change) keeps the LLM round-trip.
    pre = _RecordingPreRanker()
    quick = _RecordingQuickScoring()
    app = _make_rescore_app(pre, quick)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs", params={"tab": "boards", "min_score": 0})

    assert resp.status_code == 200
    assert pre.called is True
    # Global pre-pagination apply is always cache-only; the page-level pass does
    # the LLM round-trip on a full load / filter change (rescore defaults True).
    assert quick.llm_on_miss_calls == [False, True]


# ---------------------------------------------------------------------------
# Whole-corpus quick-score overlay gating: the pre-pagination global cache-only
# pass matters on two independent axes:
#   (a) RANKING on match-sort — a cached LLM score must be able to outrank the
#       heuristic order to reach page 1.
#   (b) FILTER MEMBERSHIP on any sort — filter_and_paginate culls by
#       match_score >= min_score BEFORE the page-level overlay ever runs, so a
#       job whose cached LLM score clears the threshold but whose heuristic
#       score doesn't would be wrongly excluded entirely (not just mis-ranked)
#       if this pass were skipped.
# The pass is gated on EITHER condition; with neither true (non-match sort,
# no active min_score) it's pure waste and is skipped. The page-level pass
# (after pagination) still runs regardless of sort, so displayed values on
# the visible page stay correct either way.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_match_sort_skips_whole_corpus_quick_overlay() -> None:
    pre = _RecordingPreRanker()
    quick = _RecordingQuickScoring()
    app = _make_rescore_app(pre, quick)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/ingestion/jobs",
            params={"tab": "boards", "sort": "title_asc", "min_score": 0},
        )

    assert resp.status_code == 200
    # Only the page-level pass fires (one call) — the whole-corpus global
    # pre-pagination overlay is skipped entirely for a non-match sort.
    assert quick.llm_on_miss_calls == [True]


@pytest.mark.asyncio
async def test_match_sort_still_runs_whole_corpus_quick_overlay() -> None:
    pre = _RecordingPreRanker()
    quick = _RecordingQuickScoring()
    app = _make_rescore_app(pre, quick)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/ingestion/jobs",
            params={"tab": "boards", "sort": "match_desc", "min_score": 0},
        )

    assert resp.status_code == 200
    # Both passes fire: the whole-corpus overlay (cache-only) then the
    # page-level pass (LLM round-trip, rescore defaults True).
    assert quick.llm_on_miss_calls == [False, True]


class _MinScoreQuickScoring:
    """Cache has 'job-low' at a HIGH score (0.9); its heuristic blend is low (0.1)."""

    def __init__(self) -> None:
        self.llm_on_miss_calls: list[bool] = []

    async def score_page(self, jobs, skills, summary, *, llm_on_miss=True):
        from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
        from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict

        self.llm_on_miss_calls.append(llm_on_miss)
        ids = {j.id for j in jobs}
        out = {}
        if "job-low" in ids:
            out["job-low"] = QuickMatchResult(
                job_id="job-low", score=0.9, verdict=QuickMatchVerdict.STRONG
            )
        return out


@pytest.mark.asyncio
async def test_non_match_sort_with_active_min_score_still_runs_whole_corpus_overlay() -> None:
    # job-low: heuristic match_score 0.1 (below the 0.5 threshold) but a
    # cached LLM quick score of 0.9 (above it). semantic_score must be set
    # (not None) for filter_and_paginate's min_score gate to actually apply
    # (jobs without a real semantic score pass through ungated).
    job_low = NormalizedJob(
        id="job-low",
        title="A Engineer",
        company="Co",
        description="d",
        skills=[],
        source="remotive",
        source_type="api",
        language="en",
        url="https://e.com/low",
        match_score=0.1,
        semantic_score=0.5,
    )
    job_high = NormalizedJob(
        id="job-high",
        title="B Engineer",
        company="Co",
        description="d",
        skills=[],
        source="remotive",
        source_type="api",
        language="en",
        url="https://e.com/high",
        match_score=0.8,
        semantic_score=0.5,
    )

    class _Orch:
        async def run(self, filters=None):
            return []

        def list_jobs(self, criteria=None):
            return [job_low, job_high]

        def persist_scores(self, *a):
            pass

        def persist_scores_batch(self, updates):
            pass

    from hiresense.ingestion.api.dependencies import get_quick_scoring

    quick = _MinScoreQuickScoring()
    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: _Orch()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileSummaryOnly()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    app.dependency_overrides[get_quick_scoring] = lambda: quick
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Non-match sort (title_asc) + an explicit min_score that job-low's
        # heuristic score fails but its cached LLM score clears.
        resp = await client.get(
            "/ingestion/jobs",
            params={"tab": "boards", "sort": "title_asc", "min_score": 0.5},
        )

    assert resp.status_code == 200
    body = resp.json()
    returned_ids = {j["id"] for j in body["jobs"]}
    # Without the overlay, job-low's heuristic 0.1 would fail min_score=0.5
    # and be dropped from the result set entirely. With it (overlay applies
    # the cached 0.9), it passes the filter -- membership, not just ranking.
    assert "job-low" in returned_ids
    # The whole-corpus overlay ran cache-only (min_score_active gate fired
    # despite the non-match sort), then the page-level pass ran normally.
    assert quick.llm_on_miss_calls == [False, True]


# ---------------------------------------------------------------------------
# #76 follow-up — cross-source ranking consistency: a job with a low heuristic
# score but a HIGH already-cached LLM score must rank to the top GLOBALLY (before
# pagination), so it isn't buried off page 1 in the all-sources view while
# surfacing only when its source is filtered. The cached LLM score is the sort
# authority wherever available.
# ---------------------------------------------------------------------------


class _SummarySection:
    content = "backend python engineer"


class _SummaryProfile:
    skills: list[str] = []
    sections = [_SummarySection()]


class FakeProfileSummaryOnly:
    async def list_profiles(self):
        return [_SummaryProfile()]


class _CachedQuickScoring:
    """Simulates 'job-gob' already LLM-scored (cached) at 0.82; 'job-hn' uncached.

    Returns the cached hit regardless of ``llm_on_miss`` — a cache hit needs no
    LLM. 'job-hn' is never returned (no cached score), so it keeps its heuristic.
    """

    def __init__(self) -> None:
        self.llm_on_miss_calls: list[bool] = []

    async def score_page(self, jobs, skills, summary, *, llm_on_miss=True):
        from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
        from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict

        self.llm_on_miss_calls.append(llm_on_miss)
        ids = {j.id for j in jobs}
        out = {}
        if "job-gob" in ids:
            out["job-gob"] = QuickMatchResult(
                job_id="job-gob", score=0.82, verdict=QuickMatchVerdict.STRONG
            )
        return out


@pytest.mark.asyncio
async def test_cached_llm_score_ranks_globally_before_pagination() -> None:
    from hiresense.ingestion.api.dependencies import get_quick_scoring

    # job-hn: high heuristic (0.78), no cached LLM score.
    # job-gob: low heuristic (0.30), but a cached LLM score of 0.82.
    # Heuristic order would bury job-gob on page 2; the cached LLM score must
    # pull it to page 1.
    job_hn = NormalizedJob(
        id="job-hn",
        title="HN Engineer",
        company="Co",
        description="d",
        skills=[],
        source="hn_hiring",
        source_type="api",
        language="en",
        url="https://e.com/hn",
        match_score=0.78,
    )
    job_gob = NormalizedJob(
        id="job-gob",
        title="Programador Back-end Python",
        company="Co",
        description="d",
        skills=[],
        source="getonboard",
        source_type="api",
        language="en",
        url="https://e.com/gob",
        match_score=0.30,
    )

    class _Orch:
        async def run(self, filters=None):
            return []

        def list_jobs(self, criteria=None):
            return [job_hn, job_gob]  # heuristic order: hn first

        def persist_scores(self, *a):
            pass

        def persist_scores_batch(self, updates):
            pass

    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: _Orch()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileSummaryOnly()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    app.dependency_overrides[get_quick_scoring] = lambda: _CachedQuickScoring()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # page_size=1: only the global #1 reaches page 1. Without the cached-LLM
        # global apply, that would be job-hn (heuristic 0.78). With it, job-gob.
        resp = await client.get(
            "/ingestion/jobs", params={"tab": "boards", "page_size": 1, "min_score": 0}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["jobs"][0]["id"] == "job-gob"  # cached LLM 0.82 outranks heuristic 0.78
    assert body["jobs"][0]["match_score"] == 0.82


# ---------------------------------------------------------------------------
# Cold-start source champions: with an EMPTY quick-score cache, the heuristic
# blend is source-biased, so page 1 of the all-sources view is monopolized by
# one source — and since only the visible page is LLM-scored, buried sources
# never get an accurate score (self-reinforcing). The fix LLM-scores the top-K
# heuristic champions of EVERY source on a full rescore, so a genuinely strong
# job from a weak-heuristic source surfaces on page 1 of the first cold load.
# ---------------------------------------------------------------------------


class _ColdChampionQuickScoring:
    """Empty cache: cache-only passes return {}. LLM passes score getonboard's
    champion at 0.9 (jobs from other sources keep their heuristic)."""

    def __init__(self) -> None:
        self.calls: list[tuple[bool, list[str]]] = []

    async def score_page(self, jobs, skills, summary, *, llm_on_miss=True):
        from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
        from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict

        self.calls.append((llm_on_miss, sorted(j.id for j in jobs)))
        if not llm_on_miss:
            return {}
        out = {}
        for j in jobs:
            if j.id == "gob-best":
                out[j.id] = QuickMatchResult(
                    job_id=j.id, score=0.9, verdict=QuickMatchVerdict.STRONG
                )
        return out


@pytest.mark.asyncio
async def test_cold_cache_source_champions_rank_globally() -> None:
    from types import SimpleNamespace

    from hiresense.ingestion.api.dependencies import get_quick_scoring

    # hn_hiring dominates the heuristic (0.7/0.6/0.5); getonboard's best job
    # has a low heuristic (0.3) but is a genuinely strong match (LLM 0.9).
    def _job(id_, source, score):
        return NormalizedJob(
            id=id_,
            title=id_,
            company="Co",
            description="d",
            skills=[],
            source=source,
            source_type="api",
            language="en",
            url=f"https://e.com/{id_}",
            match_score=score,
        )

    jobs = [
        _job("hn-1", "hn_hiring", 0.7),
        _job("hn-2", "hn_hiring", 0.6),
        _job("hn-3", "hn_hiring", 0.5),
        _job("gob-best", "getonboard", 0.3),
        _job("gob-2", "getonboard", 0.2),
    ]

    class _Orch:
        async def run(self, filters=None):
            return []

        def list_jobs(self, criteria=None):
            return list(jobs)

        def persist_scores(self, *a):
            pass

        def persist_scores_batch(self, updates):
            pass

    quick = _ColdChampionQuickScoring()
    app = FastAPI()
    app.state.settings = SimpleNamespace(
        ingestion_min_match_score=0.0,
        ingestion_max_job_age_days=0,
        ingestion_max_page_size=100,
        ingestion_source_champions_per_source=2,
    )
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: _Orch()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileSummaryOnly()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    app.dependency_overrides[get_quick_scoring] = lambda: quick
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # page_size=2: without the champions pass, hn-1/hn-2 (heuristic 0.7/0.6)
        # monopolize page 1 and gob-best is never LLM-scored at all.
        resp = await client.get(
            "/ingestion/jobs", params={"tab": "boards", "page_size": 2, "min_score": 0}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["jobs"][0]["id"] == "gob-best"
    assert body["jobs"][0]["match_score"] == 0.9
    # The champions pass scored the top-2 heuristic jobs of EVERY source
    # (cache-empty), before pagination.
    champion_call = next(c for c in quick.calls if c[0] is True)
    assert champion_call[1] == ["gob-2", "gob-best", "hn-1", "hn-2"]


# ---------------------------------------------------------------------------
# get_job detail overlay: GET /ingestion/jobs/{id} must apply the cached Tier-1
# LLM quick score (cache-only) so the detail header opens at the SAME value the
# list showed, instead of flashing the lower persisted heuristic blend before
# deep analysis arrives.
# ---------------------------------------------------------------------------


class _GetJobOrch:
    def __init__(self, job: NormalizedJob) -> None:
        self._job = job

    def get_job_by_id(self, job_id):
        return self._job if job_id == self._job.id else None


class _DetailScanner:
    def get_job_by_id(self, job_id):
        return None


def _make_get_job_app(job: NormalizedJob, quick_scoring):
    from hiresense.ingestion.api.dependencies import get_quick_scoring
    from hiresense.portfolio.api.dependencies import get_portfolio_enrichment

    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: _GetJobOrch(job)
    app.dependency_overrides[get_portal_scanner] = lambda: _DetailScanner()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileWithSkills()
    app.dependency_overrides[get_portfolio_enrichment] = lambda: None
    app.dependency_overrides[get_quick_scoring] = lambda: quick_scoring
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_get_job_overlays_cached_quick_score() -> None:
    # Persisted row carries the heuristic blend (0.30); the quick-score cache has
    # an LLM score of 0.72 for it (what the list displayed).
    job = NormalizedJob(
        id="job-detail",
        title="Engineer",
        company="Co",
        description="d",
        skills=["python"],
        source="remotive",
        source_type="api",
        language="en",
        url="https://e.com/detail",
        match_score=0.30,
    )

    class _CachedQuick:
        async def score_page(self, jobs, skills, summary, *, llm_on_miss=True):
            from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
            from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict

            assert llm_on_miss is False  # detail load must never fire the LLM
            return {
                "job-detail": QuickMatchResult(
                    job_id="job-detail", score=0.72, verdict=QuickMatchVerdict.STRONG
                )
            }

    app = _make_get_job_app(job, _CachedQuick())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs/job-detail")

    assert resp.status_code == 200
    body = resp.json()
    assert body["match_score"] == 0.72  # opens at the list's value, not 0.30
    assert body["llm_score"] == 0.72


@pytest.mark.asyncio
async def test_get_job_falls_back_to_heuristic_on_cache_miss() -> None:
    # Cold cache (job never scored): the detail view keeps the heuristic blend
    # and leaves llm_score unset rather than inventing a value.
    job = NormalizedJob(
        id="job-cold",
        title="Engineer",
        company="Co",
        description="d",
        skills=["python"],
        source="remotive",
        source_type="api",
        language="en",
        url="https://e.com/cold",
        match_score=0.30,
    )

    class _EmptyQuick:
        async def score_page(self, jobs, skills, summary, *, llm_on_miss=True):
            return {}

    app = _make_get_job_app(job, _EmptyQuick())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs/job-cold")

    assert resp.status_code == 200
    body = resp.json()
    assert body["match_score"] == 0.30
    assert body["llm_score"] is None


@pytest.mark.asyncio
async def test_requires_auth_without_token() -> None:
    """Router-level auth: requests with no bearer token are rejected."""
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs")
    assert resp.status_code == 401

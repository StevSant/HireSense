import asyncio
import json

import pytest

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict
from hiresense.ingestion.domain.quick_scoring_service import QuickScoringService


def _job(job_id: str, title: str = "Engineer") -> NormalizedJob:
    return NormalizedJob(
        id=job_id,
        title=title,
        company="Co",
        description="Build things",
        skills=["python"],
        source="remotive",
        source_type="api",
        url=f"https://example.com/{job_id}",
    )


class StubLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []
        self.systems: list[str] = []

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.calls.append(prompt)
        self.systems.append(system)
        return self.response


class StubCache:
    def __init__(self, quick: dict[str, QuickMatchResult] | None = None) -> None:
        self._quick = quick or {}
        self.upserts: list[tuple[QuickMatchResult, str]] = []
        self.bulk_upserts: list[tuple[list[QuickMatchResult], str]] = []

    def get_quick_bulk(self, job_ids, profile_hash):
        return {k: v for k, v in self._quick.items() if k in job_ids}

    def upsert_quick(self, result: QuickMatchResult, profile_hash: str) -> None:
        self.upserts.append((result, profile_hash))

    def upsert_quick_bulk(self, results: list[QuickMatchResult], profile_hash: str) -> None:
        self.bulk_upserts.append((list(results), profile_hash))
        for result in results:
            self.upserts.append((result, profile_hash))


@pytest.mark.asyncio
async def test_scores_and_caches_a_page():
    jobs = [_job("a"), _job("b")]
    response = json.dumps(
        [
            {"ref": 1, "score": 0.2, "verdict": "weak", "dealbreakers": ["Requires Java"]},
            {"ref": 2, "score": 0.8, "verdict": "strong", "reasons": ["Python backend match"]},
        ]
    )
    llm = StubLLM(response)
    cache = StubCache()
    svc = QuickScoringService(llm=llm, cache_repo=cache)

    results = await svc.score_page(jobs, ["python"], "Backend engineer")

    assert results["a"].score == 0.2
    assert results["a"].verdict is QuickMatchVerdict.WEAK
    assert results["a"].dealbreakers == ["Requires Java"]
    assert results["b"].score == 0.8
    assert results["b"].verdict is QuickMatchVerdict.STRONG
    assert len(llm.calls) == 1  # one batched call
    assert len(cache.upserts) == 2  # both persisted
    # ...via a single bulk write, not two per-result upserts.
    assert len(cache.bulk_upserts) == 1
    assert len(cache.bulk_upserts[0][0]) == 2


@pytest.mark.asyncio
async def test_only_cache_misses_are_scored():
    cached = QuickMatchResult(job_id="a", score=0.9, verdict=QuickMatchVerdict.STRONG)
    cache = StubCache({"a": cached})
    response = json.dumps([{"ref": 1, "score": 0.3, "verdict": "weak"}])
    llm = StubLLM(response)
    svc = QuickScoringService(llm=llm, cache_repo=cache)

    results = await svc.score_page([_job("a"), _job("b")], ["python"], "summary")

    assert results["a"].score == 0.9  # served from cache
    assert results["b"].score == 0.3  # freshly scored
    assert len(cache.upserts) == 1  # only the miss persisted


@pytest.mark.asyncio
async def test_no_llm_returns_only_cache_hits():
    cached = QuickMatchResult(job_id="a", score=0.5, verdict=QuickMatchVerdict.MODERATE)
    cache = StubCache({"a": cached})
    svc = QuickScoringService(llm=None, cache_repo=cache)

    results = await svc.score_page([_job("a"), _job("b")], ["python"], "summary")

    assert set(results) == {"a"}


@pytest.mark.asyncio
async def test_llm_on_miss_false_returns_only_cache_hits_without_calling_llm():
    # #76 sort-only fast path: on a pure reorder we apply already-cached quick
    # scores instantly and never fire the blocking LLM call for cache misses.
    cached = QuickMatchResult(job_id="a", score=0.9, verdict=QuickMatchVerdict.STRONG)
    cache = StubCache({"a": cached})
    llm = StubLLM(json.dumps([{"ref": 1, "score": 0.3, "verdict": "weak"}]))
    svc = QuickScoringService(llm=llm, cache_repo=cache)

    results = await svc.score_page([_job("a"), _job("b")], ["python"], "summary", llm_on_miss=False)

    assert set(results) == {"a"}  # only the cache hit; the miss is left unscored
    assert results["a"].score == 0.9
    assert llm.calls == []  # blocking LLM round-trip skipped
    assert cache.upserts == []  # nothing newly persisted


@pytest.mark.asyncio
async def test_no_profile_skips_llm():
    llm = StubLLM("[]")
    svc = QuickScoringService(llm=llm, cache_repo=StubCache())

    results = await svc.score_page([_job("a")], [], "")

    assert results == {}
    assert llm.calls == []  # never called without profile content


@pytest.mark.asyncio
async def test_malformed_response_yields_no_results():
    llm = StubLLM("the model said no")
    cache = StubCache()
    svc = QuickScoringService(llm=llm, cache_repo=cache)

    results = await svc.score_page([_job("a")], ["python"], "summary")

    assert results == {}
    assert cache.upserts == []  # nothing cached on parse failure → retried later


@pytest.mark.asyncio
async def test_candidate_block_moves_to_system_prompt_jobs_stay_in_user_prompt():
    jobs = [_job("a"), _job("b")]
    llm = StubLLM(json.dumps([{"ref": 1, "score": 0.5}, {"ref": 2, "score": 0.5}]))
    svc = QuickScoringService(llm=llm, cache_repo=StubCache())

    await svc.score_page(jobs, ["python", "sql"], "Backend engineer with 5 years")

    assert len(llm.systems) == 1
    system_prompt = llm.systems[0]
    assert "CANDIDATE" in system_prompt
    assert "Skills: python, sql" in system_prompt
    assert "Backend engineer with 5 years" in system_prompt
    # The static instructions (dealbreaker/gating rules) stay in the system
    # prompt too, ahead of the candidate block.
    assert "SENIORITY GATING" in system_prompt

    user_prompt = llm.calls[0]
    assert "CANDIDATE" not in user_prompt
    assert "JOBS" in user_prompt
    assert "Engineer @ Co" in user_prompt


@pytest.mark.asyncio
async def test_candidate_block_is_byte_stable_across_chunks():
    # 3 jobs, batch_size=1 -> 3 chunks, each scored via a separate LLM call.
    # The system prompt (static instructions + CANDIDATE block) must be
    # byte-identical across all of them since it depends only on the shared
    # candidate_skills/candidate_summary/level, not on the chunk's jobs.
    jobs = [_job(f"job-{i}") for i in range(3)]
    llm = StubLLM(json.dumps([{"ref": 1, "score": 0.5}]))
    svc = QuickScoringService(llm=llm, cache_repo=StubCache(), batch_size=1)

    await svc.score_page(jobs, ["python"], "summary")

    assert len(llm.systems) == 3
    assert len(set(llm.systems)) == 1  # identical across every chunk


@pytest.mark.asyncio
async def test_verdict_derived_when_missing():
    llm = StubLLM(json.dumps([{"ref": 1, "score": 0.85}]))
    svc = QuickScoringService(llm=llm, cache_repo=StubCache())

    results = await svc.score_page([_job("a")], ["python"], "summary")

    assert results["a"].verdict is QuickMatchVerdict.STRONG


class ConcurrencyTrackingLLM:
    """Records the max number of `.complete()` calls in flight at once.

    Holds each call open for `delay` seconds so overlapping chunk calls are
    forced to actually run concurrently (up to whatever the caller bounds
    them to) rather than happening to interleave by accident.
    """

    def __init__(self, response: str, delay: float = 0.02) -> None:
        self.response = response
        self.delay = delay
        self._current = 0
        self.max_concurrent = 0
        self._lock = asyncio.Lock()

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        async with self._lock:
            self._current += 1
            self.max_concurrent = max(self.max_concurrent, self._current)
        await asyncio.sleep(self.delay)
        async with self._lock:
            self._current -= 1
        return self.response


@pytest.mark.asyncio
async def test_semaphore_bounds_concurrent_chunk_calls():
    # 10 jobs, batch_size=1 -> 10 chunks fanned out via asyncio.gather. Without
    # a semaphore all 10 LLM calls would be in flight at once.
    jobs = [_job(f"job-{i}") for i in range(10)]
    llm = ConcurrencyTrackingLLM(response="[]")
    svc = QuickScoringService(llm=llm, cache_repo=StubCache(), batch_size=1, concurrency=3)

    await svc.score_page(jobs, ["python"], "summary")

    assert llm.max_concurrent <= 3  # never exceeds the configured cap
    assert llm.max_concurrent == 3  # and actually saturates it (bound is live, not accidental)


@pytest.mark.asyncio
async def test_concurrency_defaults_to_four():
    svc = QuickScoringService(llm=StubLLM("[]"), cache_repo=StubCache())

    assert svc._concurrency == 4


# --- #143: mismatched/reordered LLM output must not bind a score to the wrong job ---


@pytest.mark.asyncio
async def test_reordered_output_maps_by_ref_not_position():
    # Model returns the objects in a different order than the jobs were sent.
    # The `ref` must win over positional index so each score binds to its job.
    jobs = [_job("a"), _job("b")]
    response = json.dumps(
        [
            {"ref": 2, "score": 0.9, "verdict": "strong"},
            {"ref": 1, "score": 0.1, "verdict": "weak"},
        ]
    )
    svc = QuickScoringService(llm=StubLLM(response), cache_repo=StubCache())

    results = await svc.score_page(jobs, ["python"], "summary")

    assert results["a"].score == 0.1  # ref 1 -> job a, not the first array item
    assert results["b"].score == 0.9  # ref 2 -> job b


@pytest.mark.asyncio
async def test_short_refless_output_is_dropped_not_positionally_guessed():
    # 3 jobs but the model returns a single ref-less object. The old positional
    # fallback bound it to job "a"; now a count mismatch disables positional
    # guessing, so the ambiguous item is dropped rather than mis-attributed.
    jobs = [_job("a"), _job("b"), _job("c")]
    response = json.dumps([{"score": 0.9, "verdict": "strong"}])
    svc = QuickScoringService(llm=StubLLM(response), cache_repo=StubCache())

    results = await svc.score_page(jobs, ["python"], "summary")

    assert results == {}  # nothing bound; caller keeps the heuristic score


@pytest.mark.asyncio
async def test_short_output_with_valid_refs_still_maps_by_ref():
    # A count mismatch must NOT discard items that carry a usable ref — only the
    # ref-less positional guess is disabled. Jobs 1 and 3 are scored; 2 is left.
    jobs = [_job("a"), _job("b"), _job("c")]
    response = json.dumps([{"ref": 1, "score": 0.2}, {"ref": 3, "score": 0.8}])
    svc = QuickScoringService(llm=StubLLM(response), cache_repo=StubCache())

    results = await svc.score_page(jobs, ["python"], "summary")

    assert set(results) == {"a", "c"}
    assert results["a"].score == 0.2
    assert results["c"].score == 0.8


@pytest.mark.asyncio
async def test_equal_count_refless_output_still_maps_positionally():
    # The positional fallback is retained for the well-behaved 1:1 case: when
    # the array length equals the chunk length, position N maps to job N.
    jobs = [_job("a"), _job("b")]
    response = json.dumps([{"score": 0.3}, {"score": 0.7}])
    svc = QuickScoringService(llm=StubLLM(response), cache_repo=StubCache())

    results = await svc.score_page(jobs, ["python"], "summary")

    assert results["a"].score == 0.3
    assert results["b"].score == 0.7

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

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.calls.append(prompt)
        return self.response


class StubCache:
    def __init__(self, quick: dict[str, QuickMatchResult] | None = None) -> None:
        self._quick = quick or {}
        self.upserts: list[tuple[QuickMatchResult, str]] = []

    def get_quick_bulk(self, job_ids, profile_hash):
        return {k: v for k, v in self._quick.items() if k in job_ids}

    def upsert_quick(self, result: QuickMatchResult, profile_hash: str) -> None:
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
async def test_verdict_derived_when_missing():
    llm = StubLLM(json.dumps([{"ref": 1, "score": 0.85}]))
    svc = QuickScoringService(llm=llm, cache_repo=StubCache())

    results = await svc.score_page([_job("a")], ["python"], "summary")

    assert results["a"].verdict is QuickMatchVerdict.STRONG

import json

import pytest

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.matching.domain.deep_analysis_service import DeepAnalysisService


def _job(match_score: float | None = 0.42) -> NormalizedJob:
    return NormalizedJob(
        id="job-1",
        title="Senior Java Engineer",
        company="Co",
        description="Java, Spring, Postgres",
        skills=["java", "spring"],
        source="remotive",
        source_type="api",
        url="https://example.com/job-1",
        match_score=match_score,
    )


class StubLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.calls.append(prompt)
        return self.response


class StubCache:
    def __init__(self, deep: dict | None = None) -> None:
        self._deep = deep
        self.upserts: list[dict] = []

    def get_deep(self, job_id, profile_hash):
        return self._deep

    def upsert_deep(self, job_id, profile_hash, payload):
        self.upserts.append(payload)


@pytest.mark.asyncio
async def test_parses_full_analysis():
    response = json.dumps(
        {
            "overall_score": 0.25,
            "verdict": "weak",
            "dimensions": [
                {"dimension": "skills_role_fit", "score": 0.1, "rationale": "No Java"},
            ],
            "missing_skills": ["Java"],
            "cons": ["Primary language mismatch"],
            "recommendations": ["Learn Java basics"],
            "narrative": "Java is the core requirement and you don't have it.",
        }
    )
    llm = StubLLM(response)
    cache = StubCache()
    svc = DeepAnalysisService(llm=llm, cache_repo=cache)

    result = await svc.analyze(_job(), ["python"], "Python backend engineer")

    assert result.overall_score == 0.25
    assert result.verdict == "weak"
    assert result.dimensions[0].dimension == "skills_role_fit"
    assert result.missing_skills == ["Java"]
    assert len(cache.upserts) == 1  # cached for next time


@pytest.mark.asyncio
async def test_cache_hit_skips_llm():
    payload = {"job_id": "job-1", "overall_score": 0.3, "verdict": "weak"}
    llm = StubLLM("should not be called")
    svc = DeepAnalysisService(llm=llm, cache_repo=StubCache(deep=payload))

    result = await svc.analyze(_job(), ["python"], "summary")

    assert result.overall_score == 0.3
    assert llm.calls == []


@pytest.mark.asyncio
async def test_force_bypasses_cache():
    payload = {"job_id": "job-1", "overall_score": 0.3, "verdict": "weak"}
    llm = StubLLM(json.dumps({"overall_score": 0.9, "verdict": "strong"}))
    svc = DeepAnalysisService(llm=llm, cache_repo=StubCache(deep=payload))

    result = await svc.analyze(_job(), ["python"], "summary", force=True)

    assert result.overall_score == 0.9
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_no_llm_falls_back_to_heuristic():
    svc = DeepAnalysisService(llm=None, cache_repo=StubCache())

    result = await svc.analyze(_job(match_score=0.42), ["python"], "summary")

    assert result.overall_score == 0.42
    assert result.narrative  # has an explanatory note


@pytest.mark.asyncio
async def test_malformed_response_falls_back():
    llm = StubLLM("not json")
    cache = StubCache()
    svc = DeepAnalysisService(llm=llm, cache_repo=cache)

    result = await svc.analyze(_job(match_score=0.5), ["python"], "summary")

    assert result.overall_score == 0.5  # heuristic
    assert cache.upserts == []  # not cached

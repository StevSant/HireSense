from __future__ import annotations

import json

import pytest

from hiresense.ingestion.domain.job_quality import JobQuality
from hiresense.ingestion.domain.job_quality_classifier import JobQualityClassifier
from hiresense.ingestion.domain.models import NormalizedJob


def _job(job_id: str, title: str = "Backend Engineer", description: str = "Build APIs.",
         company: str = "Acme") -> NormalizedJob:
    return NormalizedJob(
        id=job_id, title=title, company=company, description=description, skills=[],
        source="weworkremotely", source_type="rss", url=f"https://e.com/{job_id}",
    )


class StubLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.calls.append(prompt)
        return self.response


@pytest.mark.asyncio
async def test_deterministic_spam_phrase_flags_without_llm() -> None:
    llm = StubLLM("[]")
    svc = JobQualityClassifier(llm=llm)
    jobs = [
        _job("a", title="Marketing Automation SaaS + Services - Line of Business Owner"),
    ]
    out = await svc.classify(jobs)
    assert out["a"].quality is JobQuality.SPAM
    assert out["a"].reason  # a concrete reason is attached
    assert llm.calls == []  # high-precision marker short-circuits the LLM


@pytest.mark.asyncio
async def test_llm_classifies_non_obvious_jobs() -> None:
    response = json.dumps(
        [
            {"ref": 1, "quality": "ok"},
            {"ref": 2, "quality": "spam", "reason": "Commission-only sales pitch"},
        ]
    )
    llm = StubLLM(response)
    svc = JobQualityClassifier(llm=llm)
    out = await svc.classify([_job("a"), _job("b", title="Sales Rep")])
    assert out["a"].quality is JobQuality.OK
    assert out["b"].quality is JobQuality.SPAM
    assert out["b"].reason == "Commission-only sales pitch"
    assert len(llm.calls) == 1  # one batched call


@pytest.mark.asyncio
async def test_no_llm_fails_open_to_ok() -> None:
    svc = JobQualityClassifier(llm=None)
    out = await svc.classify([_job("a"), _job("b")])
    assert out["a"].quality is JobQuality.OK
    assert out["b"].quality is JobQuality.OK


@pytest.mark.asyncio
async def test_llm_error_fails_open_to_ok() -> None:
    class BoomLLM:
        async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
            raise RuntimeError("llm down")

    svc = JobQualityClassifier(llm=BoomLLM())
    out = await svc.classify([_job("a")])
    assert out["a"].quality is JobQuality.OK


@pytest.mark.asyncio
async def test_unparseable_llm_response_fails_open() -> None:
    svc = JobQualityClassifier(llm=StubLLM("the model rambled"))
    out = await svc.classify([_job("a")])
    assert out["a"].quality is JobQuality.OK


@pytest.mark.asyncio
async def test_empty_input_is_noop() -> None:
    llm = StubLLM("[]")
    svc = JobQualityClassifier(llm=llm)
    assert await svc.classify([]) == {}
    assert llm.calls == []

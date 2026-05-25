from __future__ import annotations

import pytest

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService


class FakeEmbedding:
    """Returns deterministic embeddings keyed off the input text so identical
    inputs produce identical vectors and we can verify caching."""

    def __init__(self) -> None:
        self.call_count = 0
        self.batches_seen: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        self.batches_seen.append(list(texts))
        return [self._vec(t) for t in texts]

    @staticmethod
    def _vec(text: str) -> list[float]:
        # Tiny deterministic embedding: count vowels vs. consonants etc.
        vowels = sum(1 for c in text.lower() if c in "aeiou")
        cons = sum(1 for c in text.lower() if c.isalpha() and c not in "aeiou")
        spaces = text.count(" ")
        length = len(text)
        norm = max(length, 1)
        return [vowels / norm, cons / norm, spaces / norm, 1.0]


def _job(id: str, title: str = "Engineer", skills: list[str] | None = None) -> NormalizedJob:
    return NormalizedJob(
        id=id,
        title=title,
        company="Acme",
        description="Build distributed systems",
        skills=skills or ["python", "fastapi"],
        source="x",
        source_type="api",
        url=f"https://example.com/{id}",
    )


@pytest.mark.asyncio
async def test_returns_jobs_unchanged_when_no_profile() -> None:
    svc = SemanticScoringService(embedding_port=FakeEmbedding())
    jobs = [_job("a")]
    result = await svc.score_jobs(jobs, candidate_skills=[], candidate_summary="")
    assert result is jobs


@pytest.mark.asyncio
async def test_populates_semantic_score_on_every_job() -> None:
    svc = SemanticScoringService(embedding_port=FakeEmbedding())
    jobs = [_job("a"), _job("b")]
    result = await svc.score_jobs(
        jobs, candidate_skills=["python", "fastapi"], candidate_summary="Backend engineer"
    )
    assert all(j.semantic_score is not None for j in result)
    assert all(0.0 <= j.semantic_score <= 1.0 for j in result)


@pytest.mark.asyncio
async def test_caches_job_embeddings_across_calls() -> None:
    fake = FakeEmbedding()
    svc = SemanticScoringService(embedding_port=fake)
    jobs = [_job("a"), _job("b")]
    await svc.score_jobs(jobs, ["python"], "summary")
    initial_calls = fake.call_count
    # Second call: profile cached (same content), jobs cached
    await svc.score_jobs(jobs, ["python"], "summary")
    assert fake.call_count == initial_calls  # no new embedding work


@pytest.mark.asyncio
async def test_only_embeds_new_jobs_on_subsequent_call() -> None:
    fake = FakeEmbedding()
    svc = SemanticScoringService(embedding_port=fake)
    await svc.score_jobs([_job("a")], ["python"], "summary")
    fake.batches_seen.clear()
    await svc.score_jobs([_job("a"), _job("b")], ["python"], "summary")
    # Only "b" should have been embedded
    job_batches = [b for b in fake.batches_seen if b]
    assert len(job_batches) == 1
    assert len(job_batches[0]) == 1


@pytest.mark.asyncio
async def test_handles_embedding_failure_gracefully() -> None:
    class FailingEmbedding:
        async def embed(self, texts):
            raise RuntimeError("boom")

    svc = SemanticScoringService(embedding_port=FailingEmbedding())
    result = await svc.score_jobs([_job("a")], ["python"], "summary")
    # Profile embedding fails -> jobs returned unchanged
    assert result[0].semantic_score is None

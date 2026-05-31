from __future__ import annotations

import pytest

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker
from hiresense.ports.vector_store import ScoredResult


def _job(id: str) -> NormalizedJob:
    return NormalizedJob(
        id=id, title=f"Job {id}", company="Co", description="d", skills=["python"],
        source="t", source_type="api", language="en", url=f"https://e/{id}",
    )


class FakeVectorStore:
    def __init__(self) -> None:
        self.last_query: list[float] | None = None

    async def search(self, query_embedding, *, top_k=10, filters=None):
        self.last_query = query_embedding
        return [ScoredResult(id="a", score=0.9, metadata={})]

    async def upsert(self, id, embedding, metadata): ...
    async def delete(self, ids): ...
    async def get_vector(self, id): return None


class FakeEmbedding:
    async def embed(self, texts): return [[1.0, 0.0]]


class FakePreference:
    """Transforms the baseline into a fixed taste vector."""

    def query_vector(self, baseline: list[float]) -> list[float]:
        return [0.0, 1.0]


@pytest.mark.asyncio
async def test_preference_transforms_query_vector() -> None:
    store = FakeVectorStore()
    ranker = SemanticPreRanker(
        store, FakeEmbedding(), top_k_cap=10, skill_weight=0.4, semantic_weight=0.6,
        preference=FakePreference(),
    )
    await ranker.rerank([_job("a")], {"a": None}, ["python"], "summary", "boards")
    assert store.last_query == [0.0, 1.0]  # taste vector, not the raw [1.0, 0.0]


@pytest.mark.asyncio
async def test_no_preference_uses_raw_profile_vector() -> None:
    store = FakeVectorStore()
    ranker = SemanticPreRanker(
        store, FakeEmbedding(), top_k_cap=10, skill_weight=0.4, semantic_weight=0.6,
    )
    await ranker.rerank([_job("a")], {"a": None}, ["python"], "summary", "boards")
    assert store.last_query == [1.0, 0.0]  # unchanged — backward compatible


class BrokenPreference:
    def query_vector(self, baseline: list[float]) -> list[float]:
        raise RuntimeError("model unavailable")


@pytest.mark.asyncio
async def test_preference_exception_falls_back_to_baseline() -> None:
    store = FakeVectorStore()
    ranker = SemanticPreRanker(
        store, FakeEmbedding(), top_k_cap=10, skill_weight=0.4, semantic_weight=0.6,
        preference=BrokenPreference(),
    )
    await ranker.rerank([_job("a")], {"a": None}, ["python"], "summary", "boards")
    assert store.last_query == [1.0, 0.0]  # baseline used on error

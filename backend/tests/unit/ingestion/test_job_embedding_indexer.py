from __future__ import annotations

import uuid

import pytest

from hiresense.ingestion.domain.job_embedding_indexer import JobEmbeddingIndexer
from hiresense.ingestion.domain.models import NormalizedJob


def _make_job(title: str = "SWE", company: str = "Acme") -> NormalizedJob:
    return NormalizedJob(
        id=str(uuid.uuid4()),
        title=title,
        company=company,
        description="desc",
        skills=["python"],
        source="test",
        source_type="api",
        url="https://example.com",
    )


class _FakeEmbedding:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self._fail:
            raise RuntimeError("model down")
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeVectorStore:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, list[float], dict]] = []

    async def upsert(self, id: str, embedding: list[float], metadata: dict) -> None:
        self.upserts.append((id, embedding, metadata))


@pytest.mark.asyncio
async def test_index_upserts_each_job_with_bucket_metadata() -> None:
    embedding = _FakeEmbedding()
    store = _FakeVectorStore()
    indexer = JobEmbeddingIndexer(embedding, store, bucket="boards")
    jobs = [_make_job("A"), _make_job("B")]

    indexed = await indexer.index(jobs)

    assert indexed == 2
    assert len(store.upserts) == 2
    ids = {u[0] for u in store.upserts}
    assert ids == {jobs[0].id, jobs[1].id}
    for _id, vec, meta in store.upserts:
        assert vec == [0.1, 0.2, 0.3]
        assert meta == {"bucket": "boards", "source": "test"}


@pytest.mark.asyncio
async def test_index_empty_is_noop() -> None:
    embedding = _FakeEmbedding()
    store = _FakeVectorStore()
    indexer = JobEmbeddingIndexer(embedding, store, bucket="boards")

    indexed = await indexer.index([])

    assert indexed == 0
    assert embedding.calls == []
    assert store.upserts == []


@pytest.mark.asyncio
async def test_index_swallows_embedding_failure() -> None:
    embedding = _FakeEmbedding(fail=True)
    store = _FakeVectorStore()
    indexer = JobEmbeddingIndexer(embedding, store, bucket="portals")

    indexed = await indexer.index([_make_job()])

    assert indexed == 0
    assert store.upserts == []

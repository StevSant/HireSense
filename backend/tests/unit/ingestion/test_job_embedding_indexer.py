from __future__ import annotations

import logging
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
        self.deletes: list[list[str]] = []

    async def upsert(self, id: str, embedding: list[float], metadata: dict) -> None:
        self.upserts.append((id, embedding, metadata))

    async def delete(self, ids: list[str]) -> None:
        self.deletes.append(list(ids))


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
        assert meta["bucket"] == "boards" and meta["source"] == "test"
        # Carries the embedded-text hash so a later pass can skip re-encoding.
        assert meta["text_hash"]


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


@pytest.mark.asyncio
async def test_remove_deletes_from_vector_store() -> None:
    store = _FakeVectorStore()
    indexer = JobEmbeddingIndexer(embedding=_FakeEmbedding(), vector_store=store, bucket="boards")
    await indexer.remove(["j1", "j2"])
    assert store.deletes == [["j1", "j2"]]


@pytest.mark.asyncio
async def test_remove_noop_on_empty() -> None:
    store = _FakeVectorStore()
    indexer = JobEmbeddingIndexer(embedding=_FakeEmbedding(), vector_store=store, bucket="boards")
    await indexer.remove([])
    assert store.deletes == []


class _Counter:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict]] = []

    def add(self, value, attributes=None) -> None:
        self.calls.append((value, attributes or {}))


class _CountingMetrics:
    def __init__(self) -> None:
        self.automation_failures_total = _Counter()


def _patch_metrics(monkeypatch) -> _CountingMetrics:
    metrics = _CountingMetrics()
    monkeypatch.setattr(
        "hiresense.ingestion.domain.job_embedding_indexer.get_domain_metrics",
        lambda: metrics,
    )
    return metrics


@pytest.mark.asyncio
async def test_embedding_failure_is_counted_not_just_swallowed(monkeypatch) -> None:
    """Returning 0 leaves the jobs out of semantic search with nothing to retry,
    so the swallowed failure needs a signal a log line alone doesn't give."""
    metrics = _patch_metrics(monkeypatch)
    indexer = JobEmbeddingIndexer(_FakeEmbedding(fail=True), _FakeVectorStore(), bucket="portals")

    assert await indexer.index([_make_job()]) == 0
    assert metrics.automation_failures_total.calls == [(1, {"component": "job_embedding_index"})]


@pytest.mark.asyncio
async def test_upsert_failure_is_counted(monkeypatch) -> None:
    class _FailingStore(_FakeVectorStore):
        async def upsert(self, id: str, embedding: list[float], metadata: dict) -> None:
            raise RuntimeError("store down")

    metrics = _patch_metrics(monkeypatch)
    indexer = JobEmbeddingIndexer(_FakeEmbedding(), _FailingStore(), bucket="boards")

    assert await indexer.index([_make_job()]) == 0
    assert metrics.automation_failures_total.calls == [(1, {"component": "job_embedding_upsert"})]


@pytest.mark.asyncio
async def test_delete_failure_is_counted(monkeypatch) -> None:
    """A failed eviction leaves closed jobs in ANN results and nothing sweeps
    them again."""

    class _FailingStore(_FakeVectorStore):
        async def delete(self, ids: list[str]) -> None:
            raise RuntimeError("store down")

    metrics = _patch_metrics(monkeypatch)
    indexer = JobEmbeddingIndexer(_FakeEmbedding(), _FailingStore(), bucket="boards")

    await indexer.remove(["j1"])

    assert metrics.automation_failures_total.calls == [(1, {"component": "job_embedding_delete"})]


@pytest.mark.asyncio
async def test_empty_vectors_are_reported(monkeypatch, caplog) -> None:
    class _BlankEmbedding(_FakeEmbedding):
        async def embed(self, texts: list[str]) -> list[list[float]]:
            return [[] for _ in texts]

    _patch_metrics(monkeypatch)
    indexer = JobEmbeddingIndexer(_BlankEmbedding(), _FakeVectorStore(), bucket="boards")

    with caplog.at_level(
        logging.WARNING, logger="hiresense.ingestion.domain.job_embedding_indexer"
    ):
        assert await indexer.index([_make_job()]) == 0

    assert any("empty vector" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_successful_index_records_no_failure(monkeypatch) -> None:
    metrics = _patch_metrics(monkeypatch)
    indexer = JobEmbeddingIndexer(_FakeEmbedding(), _FakeVectorStore(), bucket="boards")

    assert await indexer.index([_make_job()]) == 1
    assert metrics.automation_failures_total.calls == []


class _HashingVectorStore(_FakeVectorStore):
    """Vector store that remembers metadata, like the real pgvector adapter."""

    async def get_metadata(self, ids: list[str]) -> dict[str, dict]:
        stored = {i: m for i, _v, m in self.upserts}
        return {i: stored[i] for i in ids if i in stored}


@pytest.mark.asyncio
async def test_unchanged_jobs_are_not_re_embedded() -> None:
    job = _make_job()
    embedding = _FakeEmbedding()
    store = _HashingVectorStore()
    indexer = JobEmbeddingIndexer(embedding, store, bucket="boards")

    assert await indexer.index([job]) == 1
    assert await indexer.index([job]) == 0

    # Second pass embeds nothing and leaves the stored vector untouched.
    assert len(embedding.calls) == 1
    assert len(store.upserts) == 1


@pytest.mark.asyncio
async def test_changed_text_is_re_embedded() -> None:
    job = _make_job(title="SWE")
    embedding = _FakeEmbedding()
    store = _HashingVectorStore()
    indexer = JobEmbeddingIndexer(embedding, store, bucket="boards")
    await indexer.index([job])

    changed = job.model_copy(update={"title": "Staff SWE"})
    assert await indexer.index([changed]) == 1
    assert len(embedding.calls) == 2


@pytest.mark.asyncio
async def test_only_the_stale_subset_is_embedded() -> None:
    a, b = _make_job(title="A"), _make_job(title="B")
    embedding = _FakeEmbedding()
    store = _HashingVectorStore()
    indexer = JobEmbeddingIndexer(embedding, store, bucket="boards")
    await indexer.index([a])
    embedding.calls.clear()

    assert await indexer.index([a, b]) == 1
    # Exactly one text embedded — b's — not the whole pair.
    assert embedding.calls == [[_job_text_of(b)]]


def _job_text_of(job: NormalizedJob) -> str:
    from hiresense.ingestion.domain.embedding_text import job_text

    return job_text(job)


@pytest.mark.asyncio
async def test_store_without_metadata_support_still_embeds_everything() -> None:
    """A store that cannot report hashes must not silently skip indexing."""
    job = _make_job()
    embedding = _FakeEmbedding()
    store = _FakeVectorStore()  # no get_metadata
    indexer = JobEmbeddingIndexer(embedding, store, bucket="boards")

    assert await indexer.index([job]) == 1
    assert await indexer.index([job]) == 1
    assert len(embedding.calls) == 2


@pytest.mark.asyncio
async def test_metadata_lookup_failure_falls_back_to_embedding_all() -> None:
    class _Broken(_FakeVectorStore):
        async def get_metadata(self, ids: list[str]) -> dict[str, dict]:
            raise RuntimeError("db down")

    job = _make_job()
    embedding = _FakeEmbedding()
    indexer = JobEmbeddingIndexer(embedding, _Broken(), bucket="boards")

    assert await indexer.index([job]) == 1
    assert len(embedding.calls) == 1


@pytest.mark.asyncio
async def test_vector_without_text_hash_is_treated_as_stale() -> None:
    """Vectors written before this change carry no hash and must be refreshed."""

    class _Legacy(_FakeVectorStore):
        async def get_metadata(self, ids: list[str]) -> dict[str, dict]:
            return {i: {"bucket": "boards", "source": "test"} for i in ids}

    job = _make_job()
    embedding = _FakeEmbedding()
    indexer = JobEmbeddingIndexer(embedding, _Legacy(), bucket="boards")

    assert await indexer.index([job]) == 1
    assert len(embedding.calls) == 1

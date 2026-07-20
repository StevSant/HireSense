"""SQL-construction tests for PgVectorStore.

These verify the adapter builds the right statements/parameters without a real
Postgres (pgvector can't run on the sqlite test DB). The actual `<=>` ranking and
extension behaviour must be validated against a real pgvector instance.
"""

from __future__ import annotations

import json
import threading

import pytest

from hiresense.adapters.vector_store import PgVectorStore
from hiresense.ports.vector_store import ScoredResult


class _Row:
    def __init__(self, id: str, metadata: dict, score: float) -> None:
        self.id = id
        self.metadata = metadata
        self.score = score


class _VectorRow:
    def __init__(self, embedding: str | None) -> None:
        self.embedding = embedding


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, rows: list | None = None) -> None:
        self.executed: list[tuple[str, dict]] = []
        self.commits = 0
        # Thread identity each `execute()` call ran on — used to prove the
        # sync SQLAlchemy work is offloaded off the event-loop thread.
        self.threads: list[int] = []
        self._rows = rows or []

    def execute(self, stmt, params=None):
        self.threads.append(threading.get_ident())
        self.executed.append((str(stmt), params or {}))
        return _FakeResult(self._rows)

    def commit(self) -> None:
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeSessionFactory:
    def __init__(self, rows: list[_Row] | None = None) -> None:
        self.session = _FakeSession(rows)

    def __call__(self):
        return self.session


@pytest.mark.asyncio
async def test_upsert_builds_insert_on_conflict() -> None:
    factory = _FakeSessionFactory()
    store = PgVectorStore(factory, dim=3)

    await store.upsert("job-1", [0.1, 0.2, 0.3], {"bucket": "boards"})

    sql, params = factory.session.executed[0]
    assert "INSERT INTO vector_embeddings" in sql
    assert "ON CONFLICT (id) DO UPDATE" in sql
    assert params["id"] == "job-1"
    assert params["embedding"] == "[0.1,0.2,0.3]"
    assert json.loads(params["metadata"]) == {"bucket": "boards"}
    assert factory.session.commits == 1


@pytest.mark.asyncio
async def test_search_returns_scored_results_and_applies_filters() -> None:
    rows = [_Row("job-1", {"bucket": "boards"}, 0.92)]
    factory = _FakeSessionFactory(rows)
    store = PgVectorStore(factory, dim=3)

    results = await store.search([0.1, 0.2, 0.3], top_k=5, filters={"bucket": "boards"})

    assert results == [ScoredResult(id="job-1", score=0.92, metadata={"bucket": "boards"})]
    sql, params = factory.session.executed[0]
    assert "ORDER BY embedding <=>" in sql
    assert params["q"] == "[0.1,0.2,0.3]"
    assert params["k"] == 5
    assert params["fk_0"] == "bucket"
    assert params["fv_0"] == "boards"


@pytest.mark.asyncio
async def test_delete_skips_when_empty() -> None:
    factory = _FakeSessionFactory()
    store = PgVectorStore(factory, dim=3)

    await store.delete([])

    assert factory.session.executed == []


@pytest.mark.asyncio
async def test_delete_issues_in_clause() -> None:
    factory = _FakeSessionFactory()
    store = PgVectorStore(factory, dim=3)

    await store.delete(["a", "b"])

    sql, params = factory.session.executed[0]
    assert "DELETE FROM vector_embeddings" in sql
    assert params["ids"] == ["a", "b"]
    assert factory.session.commits == 1


@pytest.mark.asyncio
async def test_get_vector_returns_parsed_embedding() -> None:
    factory = _FakeSessionFactory([_VectorRow("[0.1,0.2,0.3]")])
    store = PgVectorStore(factory, dim=3)

    result = await store.get_vector("job-1")

    assert result == [0.1, 0.2, 0.3]
    sql, params = factory.session.executed[0]
    assert "SELECT embedding FROM vector_embeddings" in sql
    assert params["id"] == "job-1"


@pytest.mark.asyncio
async def test_get_vector_returns_none_when_missing() -> None:
    factory = _FakeSessionFactory([])
    store = PgVectorStore(factory, dim=3)

    result = await store.get_vector("missing")

    assert result is None


# --- Event-loop offloading -------------------------------------------------
#
# Each port method must run its sync SQLAlchemy session work in a worker
# thread (via asyncio.to_thread), not inline on the event-loop thread. The
# fake session records the thread identity each `execute()` runs on so these
# assertions actually distinguish "ran on a worker thread" from "ran inline".


@pytest.mark.asyncio
async def test_upsert_runs_off_the_event_loop_thread() -> None:
    factory = _FakeSessionFactory()
    store = PgVectorStore(factory, dim=3)
    loop_thread_id = threading.get_ident()

    await store.upsert("job-1", [0.1, 0.2, 0.3], {})

    assert factory.session.threads
    assert all(t != loop_thread_id for t in factory.session.threads)


@pytest.mark.asyncio
async def test_search_runs_off_the_event_loop_thread() -> None:
    factory = _FakeSessionFactory([_Row("job-1", {}, 0.5)])
    store = PgVectorStore(factory, dim=3)
    loop_thread_id = threading.get_ident()

    await store.search([0.1, 0.2, 0.3])

    assert factory.session.threads
    assert all(t != loop_thread_id for t in factory.session.threads)


@pytest.mark.asyncio
async def test_get_vector_runs_off_the_event_loop_thread() -> None:
    factory = _FakeSessionFactory([_VectorRow("[0.1]")])
    store = PgVectorStore(factory, dim=3)
    loop_thread_id = threading.get_ident()

    await store.get_vector("job-1")

    assert factory.session.threads
    assert all(t != loop_thread_id for t in factory.session.threads)


@pytest.mark.asyncio
async def test_delete_runs_off_the_event_loop_thread() -> None:
    factory = _FakeSessionFactory()
    store = PgVectorStore(factory, dim=3)
    loop_thread_id = threading.get_ident()

    await store.delete(["a"])

    assert factory.session.threads
    assert all(t != loop_thread_id for t in factory.session.threads)

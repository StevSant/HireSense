"""Live pgvector ANN validation — OPT-IN.

These tests exercise the REAL :class:`PgVectorStore` against the compose
Postgres+pgvector database. They are skipped by default and run only when
explicitly selected::

    docker compose up db
    export DATABASE_URL=postgresql+asyncpg://hiresense:hiresense@localhost:5432/hiresense
    uv run python -m pytest -m pgvector

The pure SQL-construction behaviour is covered by ``tests/unit/test_pgvector_adapter.py``
without a DB; this module validates the parts that only a real pgvector instance
can: the ``<=>`` cosine ranking, eviction via ``delete``, and dimension handling.
"""

from __future__ import annotations

import pytest

from hiresense.adapters.vector_store import PgVectorStore

pytestmark = pytest.mark.pgvector


def _unit_vector(dim: int, hot: int) -> list[float]:
    """A vector that is all zeros except a single 1.0 at index ``hot``.

    Distinct ``hot`` indices are mutually orthogonal, so cosine similarity to a
    query is 1.0 for the matching index and 0.0 otherwise — giving a fully
    deterministic ANN ranking independent of the index/recall behaviour.
    """
    vec = [0.0] * dim
    vec[hot % dim] = 1.0
    return vec


def _graded_vector(dim: int, hot: int, weight: float) -> list[float]:
    vec = [0.0] * dim
    vec[hot % dim] = weight
    return vec


@pytest.fixture
def store(pgvector_session_factory, embedding_dim: int) -> PgVectorStore:
    # Truncate before each test so rows from prior tests don't leak into ANN
    # results (the session-scoped table is shared across the module).
    from sqlalchemy import text

    with pgvector_session_factory() as session:
        session.execute(text("DELETE FROM vector_embeddings"))
        session.commit()
    return PgVectorStore(pgvector_session_factory, dim=embedding_dim)


async def test_upsert_then_ann_search_returns_nearest_in_order(
    store: PgVectorStore, embedding_dim: int
) -> None:
    # Three orthogonal vectors on distinct axes.
    await store.upsert("a", _unit_vector(embedding_dim, 0), {"label": "a"})
    await store.upsert("b", _unit_vector(embedding_dim, 1), {"label": "b"})
    await store.upsert("c", _unit_vector(embedding_dim, 2), {"label": "c"})

    # Query closest to axis 0 → "a" must rank first.
    results = await store.search(_unit_vector(embedding_dim, 0), top_k=3)

    # "a" is the only vector with non-zero cosine to the query → ranks first.
    # ("b" and "c" are both orthogonal to the query, so their relative order
    # is undefined and intentionally not asserted.)
    assert {r.id for r in results} == {"a", "b", "c"}
    assert results[0].id == "a"
    # Cosine similarity to the matching axis is ~1.0; orthogonal ones ~0.0.
    assert results[0].score == pytest.approx(1.0, abs=1e-4)
    assert results[0].metadata == {"label": "a"}


async def test_ann_search_ranks_by_cosine_distance(
    store: PgVectorStore, embedding_dim: int
) -> None:
    # All share axis 0 but with descending weight; cosine to a pure-axis-0 query
    # is identical for all (direction matters, not magnitude), so to get a real
    # ordering we tilt each toward a different secondary axis by a shrinking
    # amount, keeping axis 0 dominant.
    await store.upsert("near", _graded_vector(embedding_dim, 0, 1.0), {})
    mid = _graded_vector(embedding_dim, 0, 1.0)
    mid[1 % embedding_dim] = 0.3
    far = _graded_vector(embedding_dim, 0, 1.0)
    far[2 % embedding_dim] = 1.0
    await store.upsert("mid", mid, {})
    await store.upsert("far", far, {})

    results = await store.search(_unit_vector(embedding_dim, 0), top_k=3)

    ids = [r.id for r in results]
    assert ids[0] == "near"
    assert ids.index("near") < ids.index("mid") < ids.index("far")
    # Scores are monotonically non-increasing (sorted by similarity).
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


async def test_top_k_limits_result_count(store: PgVectorStore, embedding_dim: int) -> None:
    for i in range(5):
        await store.upsert(f"v{i}", _unit_vector(embedding_dim, i), {})

    results = await store.search(_unit_vector(embedding_dim, 0), top_k=2)

    assert len(results) == 2


async def test_delete_evicts_rows_from_subsequent_search(
    store: PgVectorStore, embedding_dim: int
) -> None:
    await store.upsert("keep", _unit_vector(embedding_dim, 0), {})
    await store.upsert("drop", _unit_vector(embedding_dim, 1), {})

    await store.delete(["drop"])

    results = await store.search(_unit_vector(embedding_dim, 1), top_k=10)
    ids = {r.id for r in results}
    assert "drop" not in ids
    assert "keep" in ids


async def test_get_vector_roundtrips_full_dimension(
    store: PgVectorStore, embedding_dim: int
) -> None:
    vec = _unit_vector(embedding_dim, 3)
    await store.upsert("dimcheck", vec, {})

    stored = await store.get_vector("dimcheck")

    assert stored is not None
    # Dimension handling matches settings.embedding_dim end to end.
    assert len(stored) == embedding_dim
    assert stored[3 % embedding_dim] == pytest.approx(1.0)


async def test_upsert_is_idempotent_and_updates_in_place(
    store: PgVectorStore, embedding_dim: int
) -> None:
    await store.upsert("up", _unit_vector(embedding_dim, 0), {"v": "1"})
    await store.upsert("up", _unit_vector(embedding_dim, 1), {"v": "2"})

    # Query the NEW axis → the row should now match there, and metadata updated.
    results = await store.search(_unit_vector(embedding_dim, 1), top_k=10)
    match = next(r for r in results if r.id == "up")
    assert match.metadata == {"v": "2"}
    assert match.score == pytest.approx(1.0, abs=1e-4)

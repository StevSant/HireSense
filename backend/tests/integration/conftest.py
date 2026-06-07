"""Integration-test fixtures and opt-in gating for live-DB tests.

The default suite runs entirely against in-memory SQLite (see the individual
test modules) and MUST NOT need a database. Tests marked ``pgvector`` exercise
the real Postgres+pgvector adapter and are therefore **opt-in**:

* They are skipped by default. Running ``pytest`` (no ``-m`` selector) collects
  them but the ``pytest_collection_modifyitems`` hook below attaches a skip
  marker, so they never execute and never touch a DB.
* They run only when explicitly selected with ``-m pgvector``.
* Even when selected, if the compose DB is unreachable they skip with a clear
  reason rather than erroring — so ``-m pgvector`` on a machine without the DB
  up degrades gracefully.

Workflow::

    docker compose up db
    export DATABASE_URL=postgresql+asyncpg://hiresense:hiresense@localhost:5432/hiresense
    uv run python -m pytest -m pgvector
"""
from __future__ import annotations

import os

import pytest

_PGVECTOR_MARK = "pgvector"


def _pgvector_selected(config: pytest.Config) -> bool:
    """True when the run explicitly opted into pgvector tests via ``-m pgvector``."""
    markexpr = config.getoption("-m", default="") or ""
    return _PGVECTOR_MARK in markexpr


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip pgvector-marked tests unless the run explicitly opted in.

    This makes the default ``uv run python -m pytest`` invocation green without a
    DB even when the marked module is collected (e.g. running the file directly).
    Passing ``-m pgvector`` deselects everything else and clears this skip, so the
    marked tests run (then the DB-reachability check in the fixture applies).
    """
    if _pgvector_selected(config):
        return
    skip = pytest.mark.skip(
        reason="needs a live Postgres+pgvector DB; opt in with `-m pgvector`"
    )
    for item in items:
        if _PGVECTOR_MARK in item.keywords:
            item.add_marker(skip)


def _sync_database_url() -> str:
    """Compose DB URL coerced to a sync driver for PgVectorStore.

    PgVectorStore uses a synchronous SQLAlchemy session factory, but DATABASE_URL
    in the project targets the asyncpg driver. Swap to psycopg2 (installed via
    psycopg2-binary) for the test connection.
    """
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://hiresense:hiresense@localhost:5432/hiresense",
    )
    return url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )


@pytest.fixture(scope="session")
def pgvector_session_factory():
    """A sync sessionmaker bound to the live compose DB, with the vector table ready.

    Skips (rather than errors) if the DB can't be reached or the pgvector
    extension/table can't be created. Creates the ``vector_embeddings`` table and
    HNSW index idempotently, sized to ``EMBEDDING_DIM`` (settings.embedding_dim),
    cleans rows out before/after, and drops the table at teardown so the run is
    self-contained.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import sessionmaker

    dim = int(os.environ.get("EMBEDDING_DIM", "768"))
    url = _sync_database_url()

    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:  # connection refused, auth, missing driver, etc.
        pytest.skip(f"Postgres+pgvector DB not reachable at {url!r}: {exc}")
    except Exception as exc:  # pragma: no cover - defensive (driver import errors)
        pytest.skip(f"Postgres+pgvector DB not reachable at {url!r}: {exc}")

    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS vector_embeddings ("
                    f"  id TEXT PRIMARY KEY,"
                    f"  embedding vector({dim}) NOT NULL,"
                    f"  metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb"
                    f")"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_vector_embeddings_embedding "
                    "ON vector_embeddings USING hnsw (embedding vector_cosine_ops)"
                )
            )
            conn.execute(text("DELETE FROM vector_embeddings"))
    except SQLAlchemyError as exc:
        pytest.skip(f"could not prepare vector_embeddings table: {exc}")

    factory = sessionmaker(bind=engine, expire_on_commit=False)

    yield factory

    try:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS vector_embeddings"))
    except SQLAlchemyError:
        pass
    finally:
        engine.dispose()


@pytest.fixture
def embedding_dim() -> int:
    """The configured embedding dimension (settings.embedding_dim)."""
    return int(os.environ.get("EMBEDDING_DIM", "768"))

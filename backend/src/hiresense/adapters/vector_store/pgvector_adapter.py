from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import bindparam, text

from hiresense.ports.vector_store import ScoredResult

# Default table name for the generic vector store. Kept off the ORM models so
# the heavy `vector` column type never reaches the sqlite-backed unit tests;
# the table is created by an Alembic migration and queried here via raw SQL.
_TABLE = "vector_embeddings"


def _vector_literal(embedding: list[float]) -> str:
    """pgvector text form: '[0.1,0.2,...]'."""
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


def _parse_vector(raw: str) -> list[float]:
    """Parse pgvector's text form '[0.1,0.2,...]' into floats."""
    inner = raw.strip().strip("[]").strip()
    if not inner:
        return []
    return [float(part) for part in inner.split(",")]


class PgVectorStore:
    """VectorStorePort backed by Postgres + pgvector.

    Stores `(id, embedding, metadata)` rows in a dedicated `vector_embeddings`
    table and ranks by cosine distance (`<=>`). Each async port method offloads
    its sync SQLAlchemy session work to a worker thread via `asyncio.to_thread`,
    keeping the blocking query/commit off the event loop. Vectors are bound as
    text and cast to `vector` so no driver-level pgvector type registration is
    required.
    """

    def __init__(self, session_factory: Any, *, dim: int, table: str = _TABLE) -> None:
        self._session_factory = session_factory
        self._dim = dim
        self._table = table

    async def upsert(self, id: str, embedding: list[float], metadata: dict[str, Any]) -> None:
        await asyncio.to_thread(self._upsert_sync, id, embedding, metadata)

    def _upsert_sync(self, id: str, embedding: list[float], metadata: dict[str, Any]) -> None:
        stmt = text(
            f"INSERT INTO {self._table} (id, embedding, metadata) "
            "VALUES (:id, CAST(:embedding AS vector), CAST(:metadata AS jsonb)) "
            "ON CONFLICT (id) DO UPDATE SET "
            "embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata"
        )
        with self._session_factory() as session:
            session.execute(
                stmt,
                {
                    "id": id,
                    "embedding": _vector_literal(embedding),
                    "metadata": json.dumps(metadata or {}),
                },
            )
            session.commit()

    async def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[ScoredResult]:
        return await asyncio.to_thread(self._search_sync, query_embedding, top_k, filters)

    def _search_sync(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[ScoredResult]:
        params: dict[str, Any] = {
            "q": _vector_literal(query_embedding),
            "k": top_k,
        }
        where = ""
        if filters:
            clauses = []
            for i, (key, value) in enumerate(filters.items()):
                params[f"fk_{i}"] = key
                params[f"fv_{i}"] = str(value)
                clauses.append(f"metadata->>:fk_{i} = :fv_{i}")
            where = "WHERE " + " AND ".join(clauses) + " "
        stmt = text(
            "SELECT id, metadata, "
            "1 - (embedding <=> CAST(:q AS vector)) AS score "
            f"FROM {self._table} {where}"
            "ORDER BY embedding <=> CAST(:q AS vector) "
            "LIMIT :k"
        )
        with self._session_factory() as session:
            rows = session.execute(stmt, params).all()
        return [
            ScoredResult(
                id=row.id,
                score=float(row.score),
                metadata=row.metadata or {},
            )
            for row in rows
        ]

    async def get_vector(self, id: str) -> list[float] | None:
        return await asyncio.to_thread(self._get_vector_sync, id)

    def _get_vector_sync(self, id: str) -> list[float] | None:
        stmt = text(f"SELECT embedding FROM {self._table} WHERE id = :id")
        with self._session_factory() as session:
            row = session.execute(stmt, {"id": id}).first()
        if row is None or row.embedding is None:
            return None
        return _parse_vector(str(row.embedding))

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        await asyncio.to_thread(self._delete_sync, ids)

    def _delete_sync(self, ids: list[str]) -> None:
        stmt = text(f"DELETE FROM {self._table} WHERE id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        )
        with self._session_factory() as session:
            session.execute(stmt, {"ids": ids})
            session.commit()

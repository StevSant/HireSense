from __future__ import annotations

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


class PgVectorStore:
    """VectorStorePort backed by Postgres + pgvector.

    Stores `(id, embedding, metadata)` rows in a dedicated `vector_embeddings`
    table and ranks by cosine distance (`<=>`). The async port methods run the
    sync query inline, matching the rest of the persistence layer's
    sync-session-in-async-handler pattern. Vectors are bound as text and cast to
    `vector` so no driver-level pgvector type registration is required.
    """

    def __init__(self, session_factory: Any, *, dim: int, table: str = _TABLE) -> None:
        self._session_factory = session_factory
        self._dim = dim
        self._table = table

    async def upsert(
        self, id: str, embedding: list[float], metadata: dict[str, Any]
    ) -> None:
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

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        stmt = text(f"DELETE FROM {self._table} WHERE id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        )
        with self._session_factory() as session:
            session.execute(stmt, {"ids": ids})
            session.commit()

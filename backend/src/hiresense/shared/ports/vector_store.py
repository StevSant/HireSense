from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ScoredResult:
    id: str
    score: float
    metadata: dict[str, Any]


VectorUpsert = tuple[str, list[float], dict[str, Any]]


class VectorStorePort(Protocol):
    async def upsert(self, id: str, embedding: list[float], metadata: dict[str, Any]) -> None: ...

    async def upsert_many(self, items: list[VectorUpsert]) -> None: ...

    async def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[ScoredResult]: ...

    async def delete(self, ids: list[str]) -> None: ...

    async def get_vector(self, id: str) -> list[float] | None: ...

    async def get_metadata(self, ids: list[str]) -> dict[str, dict[str, Any]]: ...

    """Stored metadata for ``ids``, keyed by id; missing ids are absent.

    One bulk read so callers can tell which vectors are already current without
    a query per id."""

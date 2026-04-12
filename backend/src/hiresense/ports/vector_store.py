from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ScoredResult:
    id: str
    score: float
    metadata: dict[str, Any]


class VectorStorePort(Protocol):
    async def upsert(
        self, id: str, embedding: list[float], metadata: dict[str, Any]
    ) -> None: ...

    async def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[ScoredResult]: ...

    async def delete(self, ids: list[str]) -> None: ...

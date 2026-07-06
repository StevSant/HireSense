from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, field_validator


class DimensionResult(BaseModel):
    dimension: str
    score: float
    rationale: str
    weight: int

    @field_validator("score")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @classmethod
    def default(
        cls, dimension: str, weight: int, rationale: str = "Not evaluated"
    ) -> DimensionResult:
        return cls(dimension=dimension, score=0.5, rationale=rationale, weight=weight)


class DimensionScorer(Protocol):
    @property
    def dimension_name(self) -> str: ...

    @property
    def weight(self) -> int: ...

    async def score(self, job: Any, profile: Any | None = None) -> DimensionResult: ...

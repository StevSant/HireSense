from __future__ import annotations

from pydantic import BaseModel, field_validator


class DeepDimension(BaseModel):
    """One scored dimension of a deep match analysis.

    `dimension` is a stable label (e.g. "seniority_fit", "skills_role_fit",
    "growth", "culture", "compensation"); `score` is 0-1; `rationale` is a
    short explanation rendered next to the dimension bar.
    """

    dimension: str
    score: float
    rationale: str = ""

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

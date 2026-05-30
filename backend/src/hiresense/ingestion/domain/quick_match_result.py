from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict


class QuickMatchResult(BaseModel):
    """Result of the Tier-1 quick (cheap-model) match scoring for one job.

    `score` is the gated 0-1 fit shown as the list percentage. `reasons` are
    short evidence bullets; `dealbreakers` are hard mismatches (seniority
    overshoot, missing primary skill, wrong discipline) surfaced as warnings.
    """

    job_id: str
    score: float
    verdict: QuickMatchVerdict
    reasons: list[str] = Field(default_factory=list)
    dealbreakers: list[str] = Field(default_factory=list)

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

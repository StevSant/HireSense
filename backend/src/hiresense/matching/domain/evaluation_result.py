from __future__ import annotations

from pydantic import BaseModel, Field

from hiresense.matching.domain.eligibility import EligibilityResult, EligibilityStatus
from hiresense.matching.domain.scorers.base import DimensionResult


class EvaluationResult(BaseModel):
    composite_score: float
    job_title: str
    company: str
    dimensions: list[DimensionResult]
    eligibility: EligibilityResult = Field(
        default_factory=lambda: EligibilityResult(
            status=EligibilityStatus.UNKNOWN,
            rationale="Work-authorization information was not evaluated.",
        )
    )

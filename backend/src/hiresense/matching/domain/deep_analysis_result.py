from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from hiresense.matching.domain.deep_dimension import DeepDimension


class DeepAnalysisResult(BaseModel):
    """Result of the Tier-2 deep (advanced-model) single-job match analysis.

    Returned by the detail-panel analysis endpoint and cached per
    (job_id, profile_hash). Mirrors what the frontend renders: an overall
    score + verdict, a dimension breakdown, matched/missing skills, pros/cons,
    actionable recommendations, and a narrative summary.
    """

    job_id: str
    overall_score: float
    verdict: str = ""
    dimensions: list[DeepDimension] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    narrative: str = ""

    @field_validator("overall_score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

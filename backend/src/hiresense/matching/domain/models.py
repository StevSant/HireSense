from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    semantic_score: float
    skill_score: float
    experience_score: float
    language_score: float

    def weighted_average(
        self,
        weights: dict[str, float] | None = None,
    ) -> float:
        w = weights or {
            "semantic": 0.35,
            "skill": 0.30,
            "experience": 0.20,
            "language": 0.15,
        }
        total = (
            self.semantic_score * w["semantic"]
            + self.skill_score * w["skill"]
            + self.experience_score * w["experience"]
            + self.language_score * w["language"]
        )
        return round(total, 4)


class MatchResult(BaseModel):
    id: str
    job_id: str
    cv_id: str
    overall_score: float
    breakdown: ScoreBreakdown
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

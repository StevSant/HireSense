from __future__ import annotations

from pydantic import BaseModel


class MatchResultDTO(BaseModel):
    id: str
    job_id: str
    cv_id: str
    overall_score: float
    semantic_score: float
    skill_score: float
    experience_score: float
    language_score: float
    pros: list[str]
    cons: list[str]
    missing_skills: list[str]
    recommendations: list[str]

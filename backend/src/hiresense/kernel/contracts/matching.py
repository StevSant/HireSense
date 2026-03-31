from __future__ import annotations

from pydantic import BaseModel

from hiresense.kernel.events import DomainEvent


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


class MatchCompletedEvent(DomainEvent):
    event_type: str = "match.completed"
    payload: dict  # keys: job_id (str), match_id (str), score (float)

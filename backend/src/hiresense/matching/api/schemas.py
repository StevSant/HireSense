from __future__ import annotations

from pydantic import BaseModel


class EvaluateRequest(BaseModel):
    job_id: str | None = None
    profile_id: str | None = None
    job_title: str | None = None
    company: str | None = None
    description: str | None = None
    skills: list[str] = []
    location: str | None = None


class DimensionResultResponse(BaseModel):
    dimension: str
    score: float
    rationale: str
    weight: int


class EvaluationResponse(BaseModel):
    composite_score: float
    job_title: str
    company: str
    dimensions: list[DimensionResultResponse]

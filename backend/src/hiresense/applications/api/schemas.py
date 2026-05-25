from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator


class CreateApplicationRequest(BaseModel):
    """Either job_id (from ingested job) OR title+company+description (manual)."""
    job_id: uuid.UUID | None = None
    title: str | None = None
    company: str | None = None
    description: str | None = None
    url: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def check_one_of(self) -> "CreateApplicationRequest":
        if self.job_id is None:
            if not self.title or not self.company:
                raise ValueError("title and company are required when job_id is not given")
            if self.description is None:
                raise ValueError("description is required when job_id is not given")
        return self


class UpdateApplicationRequest(BaseModel):
    status: str | None = None
    notes: str | None = None


class UpdateJobSnapshotRequest(BaseModel):
    description: str | None = None
    required_skills: list[str] | None = None


class GenerateMatchRequest(BaseModel):
    cv_language: str = "en"


class GenerateOptimizationRequest(BaseModel):
    cv_language: str = "en"
    match_id: uuid.UUID | None = None


class GenerateCoverLetterRequest(BaseModel):
    cv_language: str = "en"
    tone: str = "professional"
    template_id: uuid.UUID | None = None


class ApplicationListItemResponse(BaseModel):
    id: uuid.UUID
    title: str
    company: str
    status: str
    url: str | None
    created_at: datetime | None
    has_match: bool
    has_optimization: bool
    has_prep: bool
    latest_match_score: float | None

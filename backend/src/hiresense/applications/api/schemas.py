from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator

from hiresense.tracking.domain.models import RemoteModality


class CreateApplicationRequest(BaseModel):
    """Either job_id (from ingested job) OR title+company+description (manual)."""

    job_id: uuid.UUID | None = None
    title: str | None = None
    company: str | None = None
    description: str | None = None
    url: str | None = None
    notes: str | None = None
    location: str | None = None
    remote_modality: RemoteModality | None = None
    salary_range: str | None = None
    source: str | None = None
    posted_date: datetime | None = None

    @field_validator("remote_modality", mode="before")
    @classmethod
    def normalize_onsite_alias(cls, value: object) -> object:
        return "on_site" if value == "onsite" else value

    @field_validator("location", "salary_range", "source", mode="before")
    @classmethod
    def strip_optional_metadata(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

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
    # Pipeline-view enrichment (folded in from the former Tracking page). These
    # are derived from the linked ingested job when available; they stay None for
    # manually-tracked applications with no job link.
    job_id: uuid.UUID | None = None
    notes: str | None = None
    applied_at: datetime | None = None
    location: str | None = None
    remote_modality: str | None = None
    salary_range: str | None = None
    source: str | None = None
    posted_date: datetime | None = None


class CoverLetterLibraryItem(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    title: str
    company: str
    application_url: str | None
    tone: str
    body: str
    created_at: datetime | None

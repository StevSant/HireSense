from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from hiresense.tracking.domain.models import ApplicationStatus, RemoteModality

Title = Annotated[str, Field(max_length=255)]
Company = Annotated[str, Field(max_length=255)]
ApplicationUrl = Annotated[str, Field(max_length=2048)]
ListingSource = Annotated[str, Field(max_length=100)]


def _strip_optional(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class ListingMetadataRequest(BaseModel):
    location: str | None = None
    remote_modality: RemoteModality | None = None
    salary_range: str | None = None
    source: ListingSource | None = None
    posted_date: datetime | None = None

    @field_validator("location", "salary_range", "source", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        return _strip_optional(value)

    @field_validator("remote_modality", mode="before")
    @classmethod
    def normalize_onsite_alias(cls, value: object) -> object:
        return "on_site" if value == "onsite" else value


class CreateApplicationRequest(ListingMetadataRequest):
    job_id: uuid.UUID | None = None
    title: Title | None = None
    company: Company | None = None
    url: ApplicationUrl | None = None
    notes: str | None = None


class UpdateApplicationRequest(ListingMetadataRequest):
    status: ApplicationStatus | None = None
    notes: str | None = None
    title: Title | None = None
    company: Company | None = None
    url: ApplicationUrl | None = None

    @field_validator("title", "company")
    @classmethod
    def validate_identity(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("must not be blank or null")
        return value.strip()

    @field_validator("url", "notes", mode="before")
    @classmethod
    def strip_optional_details(cls, value: object) -> object:
        return _strip_optional(value)


class TrackedApplicationResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None
    title: str
    company: str
    url: str | None
    status: ApplicationStatus
    notes: str | None
    location: str | None = None
    remote_modality: RemoteModality | None = None
    salary_range: str | None = None
    source: str | None = None
    posted_date: datetime | None = None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

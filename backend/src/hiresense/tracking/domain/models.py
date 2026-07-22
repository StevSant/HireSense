from __future__ import annotations

import enum
import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel


class ApplicationStatus(str, enum.Enum):
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RemoteModality(str, enum.Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"


class TrackedApplication(BaseModel):
    """A job application the candidate is tracking (pure domain model)."""

    id: uuid_mod.UUID | None = None
    job_id: uuid_mod.UUID | None = None
    title: str
    company: str
    url: str | None = None
    status: str = ApplicationStatus.SAVED.value
    notes: str | None = None
    location: str | None = None
    remote_modality: str | None = None
    salary_range: str | None = None
    source: str | None = None
    posted_date: datetime | None = None
    applied_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

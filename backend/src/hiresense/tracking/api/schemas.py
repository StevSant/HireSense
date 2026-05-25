from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from hiresense.tracking.domain.models import ApplicationStatus


class CreateApplicationRequest(BaseModel):
    job_id: uuid.UUID | None = None
    title: str | None = None
    company: str | None = None
    url: str | None = None
    notes: str | None = None


class UpdateApplicationRequest(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None


class TrackedApplicationResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None
    title: str
    company: str
    url: str | None
    status: ApplicationStatus
    notes: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
    location: str | None = None
    salary_range: str | None = None
    source: str | None = None
    posted_date: datetime | None = None

    model_config = {"from_attributes": True}

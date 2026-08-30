from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from hiresense.submission.domain import PageObservation, SubmissionStatus


class LeaseRequest(BaseModel):
    runner_id: str = Field(min_length=1, max_length=64)
    capacity: int = Field(default=1, ge=1, le=20)


class ObserveRequest(BaseModel):
    observation: PageObservation


class CompleteRequest(BaseModel):
    status: SubmissionStatus
    evidence: dict[str, Any] = Field(default_factory=dict)


class ResumeRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class EnqueueRequest(BaseModel):
    application_id: uuid.UUID
    job_id: str
    packet_id: uuid.UUID | None = None
    channel: str = "unknown"
    target_url: str

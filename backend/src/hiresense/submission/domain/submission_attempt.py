from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from hiresense.submission.domain.submission_status import SubmissionStatus


class SubmissionAttempt(BaseModel):
    """One attempt to submit one application to one employer form."""

    id: uuid_mod.UUID | None = None
    application_id: uuid_mod.UUID
    job_id: str
    packet_id: uuid_mod.UUID | None = None
    channel: str
    target_url: str
    status: SubmissionStatus = SubmissionStatus.QUEUED
    attempt_no: int = 1
    escalation_reason: str | None = None
    escalated_fields: list[str] = Field(default_factory=list)
    runner_id: str | None = None
    claimed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

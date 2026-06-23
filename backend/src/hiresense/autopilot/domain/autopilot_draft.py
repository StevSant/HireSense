from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel

from hiresense.autopilot.domain.draft_status import DraftStatus


class AutopilotDraft(BaseModel):
    """One job processed by an autopilot run (pure domain model)."""

    id: uuid_mod.UUID | None = None
    job_id: str
    application_id: uuid_mod.UUID | None = None
    job_title: str | None = None
    company: str | None = None
    status: DraftStatus
    detail: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

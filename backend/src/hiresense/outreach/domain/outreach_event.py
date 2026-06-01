from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel

from hiresense.outreach.domain.outreach_event_kind import OutreachEventKind


class OutreachEvent(BaseModel):
    """One recorded outreach action on a tracked application (append-only)."""

    id: uuid_mod.UUID | None = None
    application_id: uuid_mod.UUID
    kind: OutreachEventKind
    contact_name: str | None = None
    channel: str | None = None
    message: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

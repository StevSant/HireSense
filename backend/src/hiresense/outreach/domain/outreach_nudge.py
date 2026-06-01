from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel


class OutreachNudge(BaseModel):
    """A due follow-up (computed, not persisted)."""

    application_id: uuid_mod.UUID
    company: str
    contact_name: str | None
    sent_at: datetime
    days_since: int

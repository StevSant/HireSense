from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel


class StatusTransition(BaseModel):
    """One recorded application status change (pure domain model)."""

    id: uuid_mod.UUID | None = None
    application_id: uuid_mod.UUID
    from_status: str | None = None
    to_status: str
    changed_at: datetime | None = None

    model_config = {"from_attributes": True}

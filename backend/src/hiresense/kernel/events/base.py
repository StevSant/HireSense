from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

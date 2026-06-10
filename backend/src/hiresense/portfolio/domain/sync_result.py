from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SyncResult(BaseModel):
    """Outcome of one portfolio sync run across all configured sources."""

    counts_by_source: dict[str, int] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    synced_at: datetime

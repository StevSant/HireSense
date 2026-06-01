from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel, Field

from hiresense.autohunt.domain.digest_entry import DigestEntry


class Digest(BaseModel):
    """One auto-hunt run: top new matches above the floor (may be empty).

    `created_at` doubles as the watermark for the next run; `cutoff_at` is the
    "new since" lower bound this run used.
    """

    id: uuid_mod.UUID | None = None
    created_at: datetime | None = None
    cutoff_at: datetime
    entries: list[DigestEntry] = Field(default_factory=list)
    job_count: int = 0

    model_config = {"from_attributes": True}

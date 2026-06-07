from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class LLMAuditEntry:
    """Domain view of one append-only admin LLM-config audit record."""

    actor: str | None
    action: str
    target: str | None
    changes: dict = field(default_factory=dict)
    created_at: datetime | None = None
    id: uuid.UUID | None = None

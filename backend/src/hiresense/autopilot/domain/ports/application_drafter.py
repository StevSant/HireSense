from __future__ import annotations

import uuid as uuid_mod
from typing import Protocol, runtime_checkable

from hiresense.autopilot.domain.draft_status import DraftStatus


@runtime_checkable
class ApplicationDrafter(Protocol):
    """Creates an application for a job and generates its draft artifacts.
    Returns (application_id, status, detail). Implementations should not raise for
    per-artifact failures — they map those to PARTIAL/FAILED."""

    async def draft(self, job_id: str) -> tuple[uuid_mod.UUID | None, DraftStatus, str | None]: ...

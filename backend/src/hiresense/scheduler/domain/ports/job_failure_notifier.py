from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class JobFailureNotifier(Protocol):
    """Notified when a scheduled job records a FAILURE. Implementations must be
    best-effort (never raise into the caller)."""

    async def notify_job_failure(self, job_name: str, detail: str | None) -> bool: ...

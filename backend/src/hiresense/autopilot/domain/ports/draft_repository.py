from __future__ import annotations

from typing import Protocol, runtime_checkable

from hiresense.autopilot.domain.autopilot_draft import AutopilotDraft


@runtime_checkable
class DraftRepository(Protocol):
    def add(self, draft: AutopilotDraft) -> AutopilotDraft: ...

    def list(self, limit: int) -> list[AutopilotDraft]: ...

    def exists_for_job(self, job_id: str) -> bool: ...

from __future__ import annotations

from typing import Protocol, runtime_checkable

from hiresense.autopilot.domain.autopilot_draft import AutopilotDraft


@runtime_checkable
class DraftRepository(Protocol):
    def add(self, draft: AutopilotDraft) -> AutopilotDraft: ...

    def claim(self, draft: AutopilotDraft) -> AutopilotDraft | None:
        """Reserve a draft row for ``draft.job_id`` before any expensive drafting.

        Returns the persisted draft, or ``None`` when the job is already reserved
        (the unique constraint on ``job_id`` rejected the insert). This is the
        idempotency guard: a run that loses the race gets ``None`` and skips the
        job instead of duplicating the application and its LLM-generated artifacts.
        """
        ...

    def finalize(self, draft: AutopilotDraft) -> AutopilotDraft:
        """Update a previously ``claim``-ed row with the drafting outcome."""
        ...

    def list(self, limit: int) -> list[AutopilotDraft]: ...

    def exists_for_job(self, job_id: str) -> bool: ...

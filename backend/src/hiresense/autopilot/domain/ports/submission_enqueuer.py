from __future__ import annotations

from typing import Protocol

from hiresense.autopilot.domain.autopilot_draft import AutopilotDraft


class SubmissionEnqueuer(Protocol):
    """Hands a finished draft to the outbound submission queue.

    A port, so the drafting pipeline never imports the submission module and
    Phase 4 keeps working byte-identically when auto-apply is switched off.
    """

    async def enqueue_for_draft(self, draft: AutopilotDraft) -> None: ...

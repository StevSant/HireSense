from __future__ import annotations

from pydantic import BaseModel

from hiresense.autopilot.domain.autopilot_draft import AutopilotDraft


class PipelineResult(BaseModel):
    """Summary of one autopilot pipeline run."""

    created: int = 0
    skipped: int = 0
    drafts: list[AutopilotDraft] = []

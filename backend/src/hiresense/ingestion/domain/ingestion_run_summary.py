from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IngestionRunSummary(BaseModel):
    """One ingestion run plus its per-event-type totals.

    Counts are aggregated from job_history_events at read time rather than
    denormalised onto the run row, so a run's totals can never drift from the
    events that actually landed.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    started_at: datetime
    finished_at: datetime | None
    trigger: str
    status: str
    inserted: int = 0
    updated: int = 0
    reopened: int = 0
    closed: int = 0

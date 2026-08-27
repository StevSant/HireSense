from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hiresense.ingestion.domain.job_closure_reason import JobClosureReason
from hiresense.ingestion.domain.job_history_event_type import JobHistoryEventType


class JobHistoryEvent(BaseModel):
    """One observed lifecycle change to one job, before persistence.

    The recorder receives the run id once per batch rather than stamping it on
    every event before persistence. Read-side projections may populate the run
    and job context so the API can explain which fetch produced an event.
    """

    model_config = ConfigDict(frozen=True)

    job_id: str
    event: JobHistoryEventType
    changed_fields: dict[str, Any] = Field(default_factory=dict)
    reason: JobClosureReason | None = None
    occurred_at: datetime
    run_id: str | None = None
    run_trigger: str | None = None
    job_title: str | None = None
    job_company: str | None = None
    job_source: str | None = None

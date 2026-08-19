from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hiresense.ingestion.domain.job_closure_reason import JobClosureReason
from hiresense.ingestion.domain.job_history_event_type import JobHistoryEventType


class JobHistoryEvent(BaseModel):
    """One observed lifecycle change to one job, before persistence.

    Carries no run id: the recorder receives the run id once per batch rather
    than stamping it on every event.
    """

    model_config = ConfigDict(frozen=True)

    job_id: str
    event: JobHistoryEventType
    changed_fields: dict[str, Any] = Field(default_factory=dict)
    reason: JobClosureReason | None = None
    occurred_at: datetime

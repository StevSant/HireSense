from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from hiresense.scheduler.domain.job_status import JobStatus


class JobRun(BaseModel):
    """One scheduled-job invocation's recorded outcome."""

    job_name: str
    started_at: datetime
    finished_at: datetime
    status: JobStatus
    detail: str | None = None
    items_affected: int | None = None
    duration_seconds: float | None = None

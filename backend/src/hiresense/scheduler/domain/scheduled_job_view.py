from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from hiresense.scheduler.domain.job_run import JobRun


class ScheduledJobView(BaseModel):
    """Read model for the scheduler status API: a job plus its latest outcome
    and next fire time."""

    name: str
    cron: str
    enabled: bool
    last_run: JobRun | None = None
    next_run_at: datetime | None = None

from __future__ import annotations

from typing import Protocol, runtime_checkable

from hiresense.scheduler.domain.job_run import JobRun


@runtime_checkable
class JobRunRepository(Protocol):
    """Persistence port for scheduler run history."""

    def record(self, run: JobRun) -> JobRun: ...

    def recent(self, job_name: str, limit: int) -> list[JobRun]: ...

    def latest(self, job_name: str) -> JobRun | None: ...

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from hiresense.ingestion.domain import IngestionCooldownError
from hiresense.scheduler.domain.job_definition import JobDefinition
from hiresense.scheduler.domain.job_run import JobRun
from hiresense.scheduler.domain.job_status import JobStatus
from hiresense.scheduler.domain.ports import JobRunRepository, JobToggleRepository

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobRunner:
    """Runs one named job through a uniform wrapper: toggle check → invoke →
    record outcome. Never raises — a failing job is recorded and swallowed so
    one bad job can't take down the scheduler or the app. Used identically by
    the scheduled trigger and the manual run-now endpoint."""

    def __init__(
        self,
        *,
        definitions: Iterable[JobDefinition],
        run_repo: JobRunRepository,
        toggle_repo: JobToggleRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._defs = {d.name: d for d in definitions}
        self._run_repo = run_repo
        self._toggle_repo = toggle_repo
        self._clock = clock or _utcnow

    async def run(self, name: str) -> JobRun:
        defn = self._defs.get(name)
        if defn is None:
            # Never raise on an unknown job name: record a FAILURE instead so
            # the scheduler/run-now endpoint stay alive.
            now = self._clock()
            return self._record(
                name, now, now, JobStatus.FAILURE, f"unknown job: {name}", None
            )

        started = self._clock()

        if not self._toggle_repo.is_enabled(name, default=defn.default_enabled):
            # finished_at == started_at is intentional: the job never ran, so
            # the recorded duration is 0.0.
            return self._record(name, started, started, JobStatus.SKIPPED, "disabled", None)

        try:
            result = await defn.run()
        except IngestionCooldownError as exc:
            return self._record(name, started, self._clock(), JobStatus.SKIPPED, str(exc), None)
        except Exception as exc:  # noqa: BLE001 - scheduler must never crash
            logger.exception("Scheduled job %r failed", name)
            return self._record(name, started, self._clock(), JobStatus.FAILURE, str(exc), None)

        finished = self._clock()
        count = self._count(defn, result)
        return self._record(name, started, finished, JobStatus.SUCCESS, None, count)

    def _count(self, defn: JobDefinition, result: Any) -> int | None:
        try:
            return defn.count_items(result)
        except Exception:  # noqa: BLE001 - counting must never fail the run
            return None

    def _record(
        self,
        name: str,
        started: datetime,
        finished: datetime,
        status: JobStatus,
        detail: str | None,
        items: int | None,
    ) -> JobRun:
        run = JobRun(
            job_name=name,
            started_at=started,
            finished_at=finished,
            status=status,
            detail=detail,
            items_affected=items,
            duration_seconds=(finished - started).total_seconds(),
        )
        return self._run_repo.record(run)

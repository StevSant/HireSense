from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from hiresense.infrastructure import SqlRepository
from hiresense.scheduler.domain import JobRun, JobStatus
from hiresense.scheduler.infrastructure.job_run_orm import JobRunOrm


def _to_domain(row: JobRunOrm) -> JobRun:
    return JobRun(
        job_name=row.job_name,
        started_at=row.started_at,
        finished_at=row.finished_at,
        status=JobStatus(row.status),
        detail=row.detail,
        items_affected=row.items_affected,
        duration_seconds=row.duration_seconds,
    )


class JobRunRepositoryImpl(SqlRepository):
    """Run-history persistence. Prunes rows past the retention window inline on
    each insert (one bounded DELETE), so no separate maintenance job is needed."""

    def __init__(self, *, session_factory, retention_days: int) -> None:
        super().__init__(session_factory)
        self._retention_days = retention_days

    def record(self, run: JobRun) -> JobRun:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        with self._session_factory() as session:
            session.add(
                JobRunOrm(
                    job_name=run.job_name,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    status=run.status.value,
                    detail=run.detail,
                    items_affected=run.items_affected,
                    duration_seconds=run.duration_seconds,
                )
            )
            session.execute(delete(JobRunOrm).where(JobRunOrm.started_at < cutoff))
            session.commit()
        return run

    def recent(self, job_name: str, limit: int) -> list[JobRun]:
        stmt = (
            select(JobRunOrm)
            .where(JobRunOrm.job_name == job_name)
            .order_by(JobRunOrm.started_at.desc())
            .limit(limit)
        )
        return self._select_all(stmt, _to_domain)

    def latest(self, job_name: str) -> JobRun | None:
        stmt = (
            select(JobRunOrm)
            .where(JobRunOrm.job_name == job_name)
            .order_by(JobRunOrm.started_at.desc())
            .limit(1)
        )
        return self._select_one(stmt, _to_domain)

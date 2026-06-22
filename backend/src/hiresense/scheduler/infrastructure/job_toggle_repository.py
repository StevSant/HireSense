from __future__ import annotations

from sqlalchemy import select

from hiresense.infrastructure import SqlRepository
from hiresense.scheduler.infrastructure.job_toggle_orm import JobToggleOrm


class JobToggleRepositoryImpl(SqlRepository):
    """Per-job enable/disable persistence. Absent row → caller's default."""

    def is_enabled(self, job_name: str, default: bool) -> bool:
        with self._session_factory() as session:
            row = session.get(JobToggleOrm, job_name)
            return row.enabled if row is not None else default

    def set_enabled(self, job_name: str, enabled: bool) -> None:
        with self._session_factory() as session:
            row = session.get(JobToggleOrm, job_name)
            if row is None:
                session.add(JobToggleOrm(job_name=job_name, enabled=enabled))
            else:
                row.enabled = enabled
            session.commit()

    def all_states(self) -> dict[str, bool]:
        with self._session_factory() as session:
            rows = session.scalars(select(JobToggleOrm)).all()
            return {r.job_name: r.enabled for r in rows}

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select

from hiresense.ingestion.domain.ingestion_run_summary import IngestionRunSummary
from hiresense.ingestion.domain.job_history_event import JobHistoryEvent
from hiresense.ingestion.infrastructure.ingestion_run_orm import IngestionRunOrm
from hiresense.ingestion.infrastructure.job_history_event_orm import JobHistoryEventOrm
from hiresense.shared.infrastructure.sql_repository import SqlRepository


def _to_domain(row: JobHistoryEventOrm) -> JobHistoryEvent:
    return JobHistoryEvent(
        job_id=row.job_id,
        event=row.event,
        changed_fields=row.changed_fields or {},
        reason=row.reason,
        occurred_at=row.occurred_at,
    )


class JobHistoryRepository(SqlRepository):
    """The only SQL for the audit trail.

    Run totals are aggregated from job_history_events at read time rather than
    denormalised onto the run row, so a run's counts can never disagree with
    the events that actually landed.
    """

    def start_run(self, trigger: str, started_at: datetime) -> str:
        run_id = uuid_mod.uuid4()
        with self._session_factory() as session:
            session.add(
                IngestionRunOrm(id=run_id, started_at=started_at, trigger=trigger, status="running")
            )
            session.commit()
        return str(run_id)

    def finish_run(self, run_id: str, status: str, finished_at: datetime) -> None:
        with self._session_factory() as session:
            row = session.get(IngestionRunOrm, uuid_mod.UUID(run_id))
            if row is None:
                return
            row.status = status
            row.finished_at = finished_at
            session.commit()

    def insert_events(self, run_id: str | None, events: list[JobHistoryEvent]) -> None:
        if not events:
            return
        resolved = uuid_mod.UUID(run_id) if run_id else None
        with self._session_factory() as session:
            # One executemany for the whole batch: a fetch produces ~1,000+
            # events per cycle and per-row inserts would dominate the pass.
            session.execute(
                JobHistoryEventOrm.__table__.insert(),
                [
                    {
                        "id": uuid_mod.uuid4(),
                        "job_id": e.job_id,
                        "run_id": resolved,
                        "event": e.event.value,
                        "changed_fields": e.changed_fields,
                        "reason": e.reason.value if e.reason else None,
                        "occurred_at": e.occurred_at,
                    }
                    for e in events
                ],
            )
            session.commit()

    def list_events_for_job(self, job_id: str, limit: int) -> list[JobHistoryEvent]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(JobHistoryEventOrm)
                .where(JobHistoryEventOrm.job_id == job_id)
                .order_by(JobHistoryEventOrm.occurred_at.desc())
                .limit(limit)
            ).all()
            return [_to_domain(r) for r in rows]

    def list_events_for_run(self, run_id: str, limit: int) -> list[JobHistoryEvent]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(JobHistoryEventOrm)
                .where(JobHistoryEventOrm.run_id == uuid_mod.UUID(run_id))
                .order_by(JobHistoryEventOrm.occurred_at.desc())
                .limit(limit)
            ).all()
            return [_to_domain(r) for r in rows]

    def list_runs(self, limit: int, offset: int) -> list[IngestionRunSummary]:
        with self._session_factory() as session:
            runs = session.scalars(
                select(IngestionRunOrm)
                .order_by(IngestionRunOrm.started_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            if not runs:
                return []
            # One grouped count for the whole page instead of a query per run.
            counts = self._counts_for(session, [r.id for r in runs])
            return [self._summary(r, counts.get(r.id, {})) for r in runs]

    def get_run(self, run_id: str) -> IngestionRunSummary | None:
        resolved = uuid_mod.UUID(run_id)
        with self._session_factory() as session:
            row = session.get(IngestionRunOrm, resolved)
            if row is None:
                return None
            counts = self._counts_for(session, [resolved])
            return self._summary(row, counts.get(resolved, {}))

    def prune_events_older_than(self, cutoff: datetime) -> int:
        with self._session_factory() as session:
            result = session.execute(
                delete(JobHistoryEventOrm).where(JobHistoryEventOrm.occurred_at < cutoff)
            )
            session.commit()
            return int(result.rowcount or 0)

    @staticmethod
    def _counts_for(session: Any, run_ids: list[uuid_mod.UUID]) -> dict[Any, dict[str, int]]:
        rows = session.execute(
            select(
                JobHistoryEventOrm.run_id,
                JobHistoryEventOrm.event,
                func.count().label("total"),
            )
            .where(JobHistoryEventOrm.run_id.in_(run_ids))
            .group_by(JobHistoryEventOrm.run_id, JobHistoryEventOrm.event)
        ).all()
        counts: dict[Any, dict[str, int]] = {}
        for run_id, event, total in rows:
            counts.setdefault(run_id, {})[event] = total
        return counts

    @staticmethod
    def _summary(row: IngestionRunOrm, counts: dict[str, int]) -> IngestionRunSummary:
        return IngestionRunSummary(
            id=str(row.id),
            started_at=row.started_at,
            finished_at=row.finished_at,
            trigger=row.trigger,
            status=row.status,
            inserted=counts.get("inserted", 0),
            updated=counts.get("updated", 0),
            reopened=counts.get("reopened", 0),
            closed=counts.get("closed", 0),
        )

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select

from hiresense.shared.infrastructure import SqlRepository
from hiresense.submission.domain import (
    SubmissionAttempt,
    SubmissionEvent,
    SubmissionEventKind,
    SubmissionStatus,
)
from hiresense.submission.infrastructure.submission_attempt_orm import SubmissionAttemptOrm
from hiresense.submission.infrastructure.submission_event_orm import SubmissionEventOrm

_LEASED = (SubmissionStatus.CLAIMED.value, SubmissionStatus.IN_PROGRESS.value)


def _to_domain(row: SubmissionAttemptOrm) -> SubmissionAttempt:
    return SubmissionAttempt(
        id=row.id,
        application_id=row.application_id,
        job_id=row.job_id,
        packet_id=row.packet_id,
        channel=row.channel,
        target_url=row.target_url,
        status=SubmissionStatus(row.status),
        attempt_no=row.attempt_no,
        escalation_reason=row.escalation_reason,
        escalated_fields=list(row.escalated_fields or []),
        runner_id=row.runner_id,
        claimed_at=row.claimed_at,
        lease_expires_at=row.lease_expires_at,
        evidence=dict(row.evidence or {}),
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
    )


def _event_to_domain(row: SubmissionEventOrm) -> SubmissionEvent:
    return SubmissionEvent(
        id=row.id,
        attempt_id=row.attempt_id,
        seq=row.seq,
        kind=SubmissionEventKind(row.kind),
        payload=dict(row.payload or {}),
        created_at=row.created_at,
    )


def _new_orm(attempt: SubmissionAttempt) -> SubmissionAttemptOrm:
    return SubmissionAttemptOrm(
        application_id=attempt.application_id,
        job_id=attempt.job_id,
        packet_id=attempt.packet_id,
        channel=attempt.channel,
        target_url=attempt.target_url,
        status=attempt.status.value,
        attempt_no=attempt.attempt_no,
        escalation_reason=attempt.escalation_reason,
        escalated_fields=list(attempt.escalated_fields),
        runner_id=attempt.runner_id,
        claimed_at=attempt.claimed_at,
        lease_expires_at=attempt.lease_expires_at,
        evidence=dict(attempt.evidence),
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
    )


class SubmissionRepositoryImpl(SqlRepository):
    def create(self, attempt: SubmissionAttempt) -> SubmissionAttempt:
        return self._insert(_new_orm(attempt), _to_domain)

    def get(self, attempt_id: uuid.UUID) -> SubmissionAttempt | None:
        return self._get_by_pk(SubmissionAttemptOrm, attempt_id, _to_domain)

    def list(
        self, status: SubmissionStatus | None = None, limit: int = 50
    ) -> list[SubmissionAttempt]:
        stmt = select(SubmissionAttemptOrm)
        if status is not None:
            stmt = stmt.where(SubmissionAttemptOrm.status == status.value)
        stmt = stmt.order_by(SubmissionAttemptOrm.created_at.desc()).limit(limit)
        return self._select_all(stmt, _to_domain)

    def update(self, attempt: SubmissionAttempt) -> SubmissionAttempt:
        updated = self._update_by_pk(
            SubmissionAttemptOrm,
            attempt.id,
            {
                "status": attempt.status.value,
                "attempt_no": attempt.attempt_no,
                "packet_id": attempt.packet_id,
                "escalation_reason": attempt.escalation_reason,
                "escalated_fields": list(attempt.escalated_fields),
                "runner_id": attempt.runner_id,
                "claimed_at": attempt.claimed_at,
                "lease_expires_at": attempt.lease_expires_at,
                "evidence": dict(attempt.evidence),
                "started_at": attempt.started_at,
                "finished_at": attempt.finished_at,
            },
            _to_domain,
        )
        if updated is None:  # pragma: no cover - callers always hold a live row
            raise RuntimeError(f"submission attempt {attempt.id} vanished before update")
        return updated

    def has_live_attempt(self, application_id: uuid.UUID) -> bool:
        terminal = [s.value for s in SubmissionStatus.terminal()]
        with self._session_factory() as session:
            stmt = (
                select(SubmissionAttemptOrm.id)
                .where(SubmissionAttemptOrm.application_id == application_id)
                .where(SubmissionAttemptOrm.status.not_in(terminal))
                .limit(1)
            )
            return session.scalars(stmt).first() is not None

    def count_created_since(self, since: datetime) -> int:
        with self._session_factory() as session:
            stmt = select(func.count(SubmissionAttemptOrm.id)).where(
                SubmissionAttemptOrm.created_at >= since
            )
            return int(session.scalars(stmt).one())

    def lease(
        self, runner_id: str, capacity: int, lease_seconds: int, now: datetime
    ) -> list[SubmissionAttempt]:
        """Claim up to `capacity` queued attempts in one transaction.

        The select-then-update runs inside a single session so two runners
        polling at the same moment cannot both claim the same row.
        """
        if capacity <= 0:
            return []
        expires = now + timedelta(seconds=lease_seconds)
        with self._session_factory() as session:
            stmt = (
                select(SubmissionAttemptOrm)
                .where(SubmissionAttemptOrm.status == SubmissionStatus.QUEUED.value)
                .order_by(SubmissionAttemptOrm.created_at.asc())
                .limit(capacity)
                .with_for_update(skip_locked=True)
            )
            rows = list(session.scalars(stmt).all())
            for row in rows:
                row.status = SubmissionStatus.CLAIMED.value
                row.runner_id = runner_id
                row.claimed_at = now
                row.lease_expires_at = expires
                if row.started_at is None:
                    row.started_at = now
            session.commit()
            return [_to_domain(session.get(SubmissionAttemptOrm, row.id)) for row in rows]

    def expire_leases(self, now: datetime, max_attempts: int) -> int:
        """Return abandoned leases to the queue, or fail them once exhausted."""
        with self._session_factory() as session:
            stmt = (
                select(SubmissionAttemptOrm)
                .where(SubmissionAttemptOrm.status.in_(_LEASED))
                .where(SubmissionAttemptOrm.lease_expires_at.is_not(None))
                .where(SubmissionAttemptOrm.lease_expires_at < now)
            )
            rows = list(session.scalars(stmt).all())
            for row in rows:
                row.runner_id = None
                row.claimed_at = None
                row.lease_expires_at = None
                if row.attempt_no >= max_attempts:
                    row.status = SubmissionStatus.FAILED.value
                    row.finished_at = now
                    row.escalation_reason = (
                        f"The runner stopped responding {row.attempt_no} times; giving up"
                    )
                else:
                    row.status = SubmissionStatus.QUEUED.value
                    row.attempt_no = row.attempt_no + 1
            session.commit()
            return len(rows)

    def append_event(self, event: SubmissionEvent) -> SubmissionEvent:
        row = SubmissionEventOrm(
            attempt_id=event.attempt_id,
            seq=event.seq,
            kind=event.kind.value,
            payload=dict(event.payload),
        )
        return self._insert(row, _event_to_domain)

    def events(self, attempt_id: uuid.UUID) -> list[SubmissionEvent]:
        stmt = (
            select(SubmissionEventOrm)
            .where(SubmissionEventOrm.attempt_id == attempt_id)
            .order_by(SubmissionEventOrm.seq.asc())
        )
        return self._select_all(stmt, _event_to_domain)

    def next_seq(self, attempt_id: uuid.UUID) -> int:
        with self._session_factory() as session:
            stmt = select(func.max(SubmissionEventOrm.seq)).where(
                SubmissionEventOrm.attempt_id == attempt_id
            )
            current = session.scalars(stmt).one()
            return 0 if current is None else int(current) + 1

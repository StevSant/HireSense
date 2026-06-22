from __future__ import annotations

import uuid as uuid_mod

from sqlalchemy import select

from hiresense.infrastructure import SqlRepository
from hiresense.inbox.domain import DetectedSignal, EmailSignalKind, SignalState
from hiresense.inbox.infrastructure.detected_signal_orm import DetectedSignalOrm


def _to_domain(row: DetectedSignalOrm) -> DetectedSignal:
    return DetectedSignal(
        id=row.id,
        message_id=row.message_id,
        from_address=row.from_address,
        subject=row.subject,
        received_at=row.received_at,
        kind=EmailSignalKind(row.kind),
        company=row.company,
        role=row.role,
        confidence=row.confidence,
        matched_application_id=row.matched_application_id,
        proposed_status=row.proposed_status,
        state=SignalState(row.state),
        created_at=row.created_at,
    )


class DetectedSignalRepositoryImpl(SqlRepository):
    def add(self, signal: DetectedSignal) -> DetectedSignal:
        row = DetectedSignalOrm(
            message_id=signal.message_id,
            from_address=signal.from_address,
            subject=signal.subject,
            received_at=signal.received_at,
            kind=signal.kind.value,
            company=signal.company,
            role=signal.role,
            confidence=signal.confidence,
            matched_application_id=signal.matched_application_id,
            proposed_status=signal.proposed_status,
            state=signal.state.value,
        )
        return self._insert(row, _to_domain)

    def list(self, state: SignalState | None = None) -> list[DetectedSignal]:
        stmt = select(DetectedSignalOrm).order_by(DetectedSignalOrm.received_at.desc())
        if state is not None:
            stmt = stmt.where(DetectedSignalOrm.state == state.value)
        return self._select_all(stmt, _to_domain)

    def get(self, id: uuid_mod.UUID) -> DetectedSignal | None:
        return self._get_by_pk(DetectedSignalOrm, id, _to_domain)

    def set_state(self, id: uuid_mod.UUID, state: SignalState) -> DetectedSignal | None:
        return self._update_by_pk(DetectedSignalOrm, id, {"state": state.value}, _to_domain)

    def exists_message_id(self, message_id: str) -> bool:
        with self._session_factory() as session:
            stmt = select(DetectedSignalOrm.id).where(
                DetectedSignalOrm.message_id == message_id
            ).limit(1)
            return session.scalars(stmt).first() is not None

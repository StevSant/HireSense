from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.outreach.domain import OutreachEvent, OutreachEventKind
from hiresense.outreach.infrastructure.orm import OutreachEventOrm


def _to_domain(row: OutreachEventOrm) -> OutreachEvent:
    return OutreachEvent(
        id=row.id,
        application_id=row.application_id,
        kind=OutreachEventKind(row.kind),
        contact_name=row.contact_name,
        channel=row.channel,
        message=row.message,
        created_at=row.created_at,
    )


class OutreachRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def add(self, event: OutreachEvent) -> OutreachEvent:
        with self._session_factory() as session:
            row = OutreachEventOrm(
                application_id=event.application_id,
                kind=event.kind.value,
                contact_name=event.contact_name,
                channel=event.channel,
                message=event.message,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def list_for(self, application_id: uuid.UUID) -> list[OutreachEvent]:
        with self._session_factory() as session:
            stmt = (
                select(OutreachEventOrm)
                .where(OutreachEventOrm.application_id == application_id)
                .order_by(OutreachEventOrm.created_at)
            )
            return [_to_domain(r) for r in session.scalars(stmt).all()]

    def latest_for(self, application_id: uuid.UUID) -> OutreachEvent | None:
        with self._session_factory() as session:
            stmt = (
                select(OutreachEventOrm)
                .where(OutreachEventOrm.application_id == application_id)
                .order_by(OutreachEventOrm.created_at.desc())
                .limit(1)
            )
            row = session.scalars(stmt).first()
            return _to_domain(row) if row is not None else None

    def latest_per_application(self) -> list[OutreachEvent]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(OutreachEventOrm).order_by(OutreachEventOrm.created_at)
            ).all()
            # Keep the last (most recent) event per application; rows are asc by
            # created_at, so later overwrites earlier.
            latest: dict[uuid.UUID, OutreachEventOrm] = {}
            for r in rows:
                latest[r.application_id] = r
            return [_to_domain(r) for r in latest.values()]

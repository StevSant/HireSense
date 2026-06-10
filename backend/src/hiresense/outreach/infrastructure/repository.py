from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from hiresense.infrastructure import SqlRepository
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


class OutreachRepository(SqlRepository):
    def add(self, event: OutreachEvent) -> OutreachEvent:
        row = OutreachEventOrm(
            application_id=event.application_id,
            kind=event.kind.value,
            contact_name=event.contact_name,
            channel=event.channel,
            message=event.message,
        )
        return self._insert(row, _to_domain)

    def list_for(self, application_id: uuid.UUID) -> list[OutreachEvent]:
        stmt = (
            select(OutreachEventOrm)
            .where(OutreachEventOrm.application_id == application_id)
            .order_by(OutreachEventOrm.created_at)
        )
        return self._select_all(stmt, _to_domain)

    def latest_for(self, application_id: uuid.UUID) -> OutreachEvent | None:
        stmt = (
            select(OutreachEventOrm)
            .where(OutreachEventOrm.application_id == application_id)
            .order_by(OutreachEventOrm.created_at.desc())
            .limit(1)
        )
        return self._select_one(stmt, _to_domain)

    def latest_per_application(self) -> list[OutreachEvent]:
        # Latest event per application, computed in SQL (window function) so
        # the full append-only event history never has to be loaded into
        # memory. Works on both Postgres and the SQLite used in tests.
        rank = (
            func.row_number()
            .over(
                partition_by=OutreachEventOrm.application_id,
                order_by=OutreachEventOrm.created_at.desc(),
            )
            .label("rank")
        )
        ranked = select(OutreachEventOrm, rank).subquery()
        latest = aliased(OutreachEventOrm, ranked)
        stmt = select(latest).where(ranked.c.rank == 1)
        return self._select_all(stmt, _to_domain)

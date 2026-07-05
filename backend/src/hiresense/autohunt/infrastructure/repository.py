from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select

from hiresense.autohunt.domain import Digest, DigestEntry
from hiresense.autohunt.infrastructure.orm import DigestOrm
from hiresense.infrastructure import SqlRepository

# Sortable columns for the digests listing, keyed by `<field>_<dir>` token.
# Anything else falls back to newest-first.
_DIGEST_SORT_COLUMNS = {
    "created": DigestOrm.created_at,
    "count": DigestOrm.job_count,
}


def _digest_order_by(sort: str | None):
    field, _, direction = (sort or "").rpartition("_")
    column = _DIGEST_SORT_COLUMNS.get(field)
    if column is None or direction not in ("asc", "desc"):
        return DigestOrm.created_at.desc()
    return column.asc() if direction == "asc" else column.desc()


def _to_domain(row: DigestOrm) -> Digest:
    return Digest(
        id=row.id,
        created_at=row.created_at,
        cutoff_at=row.cutoff_at,
        entries=[DigestEntry.model_validate(e) for e in (row.entries or [])],
        job_count=row.job_count,
    )


class DigestRepository(SqlRepository):
    def add(self, digest: Digest) -> Digest:
        row = DigestOrm(
            cutoff_at=digest.cutoff_at,
            entries=[e.model_dump() for e in digest.entries],
            job_count=digest.job_count,
        )
        return self._insert(row, _to_domain)

    def latest(self) -> Digest | None:
        stmt = select(DigestOrm).order_by(DigestOrm.created_at.desc()).limit(1)
        return self._select_one(stmt, _to_domain)

    def list_recent(self, limit: int, sort: str | None = None) -> list[Digest]:
        stmt = select(DigestOrm).order_by(_digest_order_by(sort)).limit(limit)
        return self._select_all(stmt, _to_domain)

    def prune_older_than(self, cutoff: datetime) -> int:
        with self._session_factory() as session:
            ids = session.scalars(select(DigestOrm.id).where(DigestOrm.created_at < cutoff)).all()
            if ids:
                session.execute(delete(DigestOrm).where(DigestOrm.id.in_(ids)))
                session.commit()
            return len(ids)

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from hiresense.autohunt.domain import Digest, DigestEntry
from hiresense.autohunt.infrastructure.orm import DigestOrm


def _to_domain(row: DigestOrm) -> Digest:
    return Digest(
        id=row.id,
        created_at=row.created_at,
        cutoff_at=row.cutoff_at,
        entries=[DigestEntry.model_validate(e) for e in (row.entries or [])],
        job_count=row.job_count,
    )


class DigestRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def add(self, digest: Digest) -> Digest:
        with self._session_factory() as session:
            row = DigestOrm(
                cutoff_at=digest.cutoff_at,
                entries=[e.model_dump() for e in digest.entries],
                job_count=digest.job_count,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def latest(self) -> Digest | None:
        with self._session_factory() as session:
            stmt = select(DigestOrm).order_by(DigestOrm.created_at.desc()).limit(1)
            row = session.scalars(stmt).first()
            return _to_domain(row) if row is not None else None

    def list_recent(self, limit: int) -> list[Digest]:
        with self._session_factory() as session:
            stmt = select(DigestOrm).order_by(DigestOrm.created_at.desc()).limit(limit)
            return [_to_domain(r) for r in session.scalars(stmt).all()]

    def prune_older_than(self, cutoff: datetime) -> int:
        with self._session_factory() as session:
            ids = session.scalars(
                select(DigestOrm.id).where(DigestOrm.created_at < cutoff)
            ).all()
            if ids:
                session.execute(delete(DigestOrm).where(DigestOrm.id.in_(ids)))
                session.commit()
            return len(ids)

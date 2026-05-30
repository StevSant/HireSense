from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.infrastructure.orm import TrackedApplicationOrm

_CONTENT_FIELDS = ("job_id", "title", "company", "url", "status", "notes", "applied_at")


def _to_domain(row: TrackedApplicationOrm) -> TrackedApplication:
    return TrackedApplication.model_validate(row)


class TrackingRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get_by_id(self, id: uuid.UUID) -> TrackedApplication | None:
        with self._session_factory() as session:
            row = session.get(TrackedApplicationOrm, id)
            return _to_domain(row) if row is not None else None

    def get_by_job_id(self, job_id: uuid.UUID) -> TrackedApplication | None:
        with self._session_factory() as session:
            stmt = select(TrackedApplicationOrm).where(
                TrackedApplicationOrm.job_id == job_id
            )
            row = session.scalars(stmt).first()
            return _to_domain(row) if row is not None else None

    def list_all(self, status: ApplicationStatus | None = None) -> list[TrackedApplication]:
        with self._session_factory() as session:
            stmt = select(TrackedApplicationOrm)
            if status is not None:
                stmt = stmt.where(TrackedApplicationOrm.status == status.value)
            return [_to_domain(r) for r in session.scalars(stmt).all()]

    def create(self, application: TrackedApplication) -> TrackedApplication:
        with self._session_factory() as session:
            row = TrackedApplicationOrm(
                **{field: getattr(application, field) for field in _CONTENT_FIELDS}
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def save(self, application: TrackedApplication) -> TrackedApplication:
        with self._session_factory() as session:
            row = (
                session.get(TrackedApplicationOrm, application.id)
                if application.id
                else None
            )
            if row is None:
                row = TrackedApplicationOrm(
                    **{field: getattr(application, field) for field in _CONTENT_FIELDS}
                )
                session.add(row)
            else:
                for field in _CONTENT_FIELDS:
                    setattr(row, field, getattr(application, field))
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def delete(self, id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            row = session.get(TrackedApplicationOrm, id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

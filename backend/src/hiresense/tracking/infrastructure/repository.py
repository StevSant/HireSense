from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class TrackingRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get_by_id(self, id: uuid.UUID) -> TrackedApplication | None:
        with self._session_factory() as session:
            return session.get(TrackedApplication, id)

    def get_by_job_id(self, job_id: uuid.UUID) -> TrackedApplication | None:
        with self._session_factory() as session:
            stmt = select(TrackedApplication).where(TrackedApplication.job_id == job_id)
            return session.scalars(stmt).first()

    def list_all(self, status: ApplicationStatus | None = None) -> list[TrackedApplication]:
        with self._session_factory() as session:
            stmt = select(TrackedApplication)
            if status is not None:
                stmt = stmt.where(TrackedApplication.status == status.value)
            return list(session.scalars(stmt).all())

    def save(self, application: TrackedApplication) -> TrackedApplication:
        with self._session_factory() as session:
            application = session.merge(application)
            session.commit()
            return application

    def create(self, application: TrackedApplication) -> TrackedApplication:
        with self._session_factory() as session:
            session.add(application)
            session.commit()
            session.refresh(application)
            return application

    def delete(self, id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            app = session.get(TrackedApplication, id)
            if app is None:
                return False
            session.delete(app)
            session.commit()
            return True

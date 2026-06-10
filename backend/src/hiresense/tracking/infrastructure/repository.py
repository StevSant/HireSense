from __future__ import annotations

import uuid

from sqlalchemy import select

from hiresense.infrastructure import SqlRepository
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.domain.status_transition import StatusTransition
from hiresense.tracking.infrastructure.orm import TrackedApplicationOrm
from hiresense.tracking.infrastructure.status_history_orm import (
    ApplicationStatusHistoryOrm,
)

_CONTENT_FIELDS = ("job_id", "title", "company", "url", "status", "notes", "applied_at")


def _to_domain(row: TrackedApplicationOrm) -> TrackedApplication:
    return TrackedApplication.model_validate(row)


def _history_to_domain(row: ApplicationStatusHistoryOrm) -> StatusTransition:
    return StatusTransition.model_validate(row)


class TrackingRepository(SqlRepository):
    def get_by_id(self, id: uuid.UUID) -> TrackedApplication | None:
        return self._get_by_pk(TrackedApplicationOrm, id, _to_domain)

    def get_by_job_id(self, job_id: uuid.UUID) -> TrackedApplication | None:
        stmt = select(TrackedApplicationOrm).where(
            TrackedApplicationOrm.job_id == job_id
        )
        return self._select_one(stmt, _to_domain)

    def list_all(self, status: ApplicationStatus | None = None) -> list[TrackedApplication]:
        stmt = select(TrackedApplicationOrm)
        if status is not None:
            stmt = stmt.where(TrackedApplicationOrm.status == status.value)
        return self._select_all(stmt, _to_domain)

    def create(self, application: TrackedApplication) -> TrackedApplication:
        with self._session_factory() as session:
            row = TrackedApplicationOrm(
                **{field: getattr(application, field) for field in _CONTENT_FIELDS}
            )
            session.add(row)
            session.flush()  # assign row.id before writing the seed history row
            session.add(
                ApplicationStatusHistoryOrm(
                    application_id=row.id,
                    from_status=None,
                    to_status=row.status,
                )
            )
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

    def save_with_history(
        self,
        application: TrackedApplication,
        *,
        from_status: str | None,
        to_status: str,
    ) -> TrackedApplication:
        with self._session_factory() as session:
            row = (
                session.get(TrackedApplicationOrm, application.id)
                if application.id
                else None
            )
            if row is None:
                # Defensive mirror of save() for an unpersisted app. Not the
                # seeding path: the sole caller (update_status) always passes a
                # persisted app, so new applications are seeded via create().
                row = TrackedApplicationOrm(
                    **{field: getattr(application, field) for field in _CONTENT_FIELDS}
                )
                session.add(row)
                session.flush()
            else:
                for field in _CONTENT_FIELDS:
                    setattr(row, field, getattr(application, field))
            session.add(
                ApplicationStatusHistoryOrm(
                    application_id=row.id,
                    from_status=from_status,
                    to_status=to_status,
                )
            )
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def delete(self, id: uuid.UUID) -> bool:
        return self._delete_by_pk(TrackedApplicationOrm, id)

    def list_history(self) -> list[StatusTransition]:
        stmt = select(ApplicationStatusHistoryOrm).order_by(
            ApplicationStatusHistoryOrm.changed_at
        )
        return self._select_all(stmt, _history_to_domain)

    def history_for(self, application_id: uuid.UUID) -> list[StatusTransition]:
        stmt = (
            select(ApplicationStatusHistoryOrm)
            .where(ApplicationStatusHistoryOrm.application_id == application_id)
            .order_by(ApplicationStatusHistoryOrm.changed_at)
        )
        return self._select_all(stmt, _history_to_domain)

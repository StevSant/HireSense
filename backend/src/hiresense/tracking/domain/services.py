from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from hiresense.kernel.events import TrackingStatusChangedEvent
from hiresense.kernel.exceptions import ConflictError, NotFoundError
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.domain.status_transition_policy import ensure_valid_transition

if TYPE_CHECKING:
    from hiresense.tracking.ports import TrackingRepositoryPort


class TrackingService:
    def __init__(
        self, repository: TrackingRepositoryPort, ingestion_orchestrator: Any, event_bus: Any
    ) -> None:
        self._repo = repository
        self._ingestion = ingestion_orchestrator
        self._event_bus = event_bus

    def track_job(
        self,
        title: str,
        company: str,
        url: str | None = None,
        notes: str | None = None,
    ) -> TrackedApplication:
        app = TrackedApplication(
            title=title,
            company=company,
            url=url,
            notes=notes,
            status=ApplicationStatus.SAVED.value,
        )
        return self._repo.create(app)

    def track_from_ingestion(self, job_id: str) -> TrackedApplication:
        job = self._ingestion.get_job_by_id(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")
        job_uuid = uuid_mod.UUID(job_id)
        existing = self._repo.get_by_job_id(job_uuid)
        if existing is not None:
            raise ConflictError("This job is already tracked")
        app = TrackedApplication(
            job_id=job_uuid,
            title=job.title,
            company=job.company,
            url=getattr(job, "url", None),
            status=ApplicationStatus.SAVED.value,
        )
        return self._repo.create(app)

    def get(self, id: uuid_mod.UUID) -> TrackedApplication:
        app = self._repo.get_by_id(id)
        if app is None:
            raise NotFoundError(f"Application {id} not found")
        return app

    def list(
        self,
        status: ApplicationStatus | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackedApplication]:
        return self._repo.list_all(status=status, limit=limit, offset=offset)

    def count(self, status: ApplicationStatus | None = None) -> int:
        return self._repo.count_all(status=status)

    async def update_status(
        self,
        id: uuid_mod.UUID,
        status: ApplicationStatus,
        notes: str | None = None,
    ) -> TrackedApplication:
        app = self.get(id)
        previous = app.status
        ensure_valid_transition(previous, status.value)
        app.status = status.value
        if status == ApplicationStatus.APPLIED and app.applied_at is None:
            app.applied_at = datetime.now(timezone.utc)
        if notes is not None:
            app.notes = notes
        if previous != status.value:
            saved = self._repo.save_with_history(app, from_status=previous, to_status=status.value)
        else:
            saved = self._repo.save(app)
        if previous != saved.status and saved.job_id is not None:
            await self._event_bus.publish(
                TrackingStatusChangedEvent(job_id=str(saved.job_id), status=saved.status)
            )
        return saved

    def update_notes(self, id: uuid_mod.UUID, notes: str) -> TrackedApplication:
        app = self.get(id)
        app.notes = notes
        return self._repo.save(app)

    def remove(self, id: uuid_mod.UUID) -> None:
        deleted = self._repo.delete(id)
        if not deleted:
            raise NotFoundError(f"Application {id} not found")

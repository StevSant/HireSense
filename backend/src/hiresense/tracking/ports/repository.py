from __future__ import annotations

import uuid
from typing import Protocol

from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class TrackingRepositoryPort(Protocol):
    def get_by_id(self, id: uuid.UUID) -> TrackedApplication | None: ...

    def get_by_job_id(self, job_id: uuid.UUID) -> TrackedApplication | None: ...

    def list_all(
        self,
        status: ApplicationStatus | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackedApplication]: ...

    def count_all(self, status: ApplicationStatus | None = None) -> int: ...

    def save(self, application: TrackedApplication) -> TrackedApplication: ...

    def save_with_history(
        self,
        application: TrackedApplication,
        *,
        from_status: str | None,
        to_status: str,
    ) -> TrackedApplication: ...

    def create(self, application: TrackedApplication) -> TrackedApplication: ...

    def delete(self, id: uuid.UUID) -> bool: ...

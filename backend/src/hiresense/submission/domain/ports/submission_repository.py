from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from hiresense.submission.domain.submission_attempt import SubmissionAttempt
from hiresense.submission.domain.submission_event import SubmissionEvent
from hiresense.submission.domain.submission_status import SubmissionStatus


class SubmissionRepository(Protocol):
    """Persistence for submission attempts and their audit tape."""

    def create(self, attempt: SubmissionAttempt) -> SubmissionAttempt: ...

    def get(self, attempt_id: uuid.UUID) -> SubmissionAttempt | None: ...

    def list(
        self, status: SubmissionStatus | None = None, limit: int = 50
    ) -> list[SubmissionAttempt]: ...

    def update(self, attempt: SubmissionAttempt) -> SubmissionAttempt: ...

    def has_live_attempt(self, application_id: uuid.UUID) -> bool: ...

    def count_created_since(self, since: datetime) -> int: ...

    def lease(
        self, runner_id: str, capacity: int, lease_seconds: int, now: datetime
    ) -> list[SubmissionAttempt]: ...

    def expire_leases(self, now: datetime, max_attempts: int) -> int: ...

    def append_event(self, event: SubmissionEvent) -> SubmissionEvent: ...

    def events(self, attempt_id: uuid.UUID) -> list[SubmissionEvent]: ...

    def next_seq(self, attempt_id: uuid.UUID) -> int: ...

from __future__ import annotations

from hiresense.kernel.events.base import DomainEvent


class TrackingStatusChangedEvent(DomainEvent):
    """Emitted when a tracked application's status actually changes.

    ``job_id`` is the ingestion job id as a string (None when the tracked
    application is not linked to an ingested job — such events carry no
    embedding-mappable target and are ignored by the preference subscriber).
    """

    event_type: str = "tracking.status_changed"
    job_id: str | None
    status: str

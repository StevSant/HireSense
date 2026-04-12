from __future__ import annotations

from hiresense.kernel.events.base import DomainEvent


class JobsIngestedEvent(DomainEvent):
    event_type: str = "jobs.ingested"
    job_ids: list[str]
    source: str

from __future__ import annotations

from hiresense.kernel.events import DomainEvent


class JobsIngestedEvent(DomainEvent):
    event_type: str = "jobs.ingested"
    payload: dict  # keys: job_ids (list[str]), source (str)

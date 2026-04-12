from __future__ import annotations

from hiresense.kernel.events.base import DomainEvent


class MatchCompletedEvent(DomainEvent):
    event_type: str = "match.completed"
    job_id: str
    match_id: str
    score: float

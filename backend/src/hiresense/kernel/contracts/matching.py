"""Backward-compatible re-export. Import from kernel.schemas or kernel.events."""

from hiresense.kernel.events.match_completed import MatchCompletedEvent
from hiresense.kernel.schemas.match_result_dto import MatchResultDTO

__all__ = ["MatchCompletedEvent", "MatchResultDTO"]

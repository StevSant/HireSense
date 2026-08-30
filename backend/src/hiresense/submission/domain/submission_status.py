from __future__ import annotations

import enum


class SubmissionStatus(str, enum.Enum):
    """Lifecycle of one attempt to submit one application."""

    QUEUED = "queued"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    SUBMITTED = "submitted"
    FAILED = "failed"
    ABANDONED = "abandoned"

    @classmethod
    def terminal(cls) -> frozenset["SubmissionStatus"]:
        """Statuses an attempt never moves out of."""
        return frozenset({cls.SUBMITTED, cls.FAILED, cls.ABANDONED})

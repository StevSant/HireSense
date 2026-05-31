from __future__ import annotations

from hiresense.preference.domain.feedback_kind import FeedbackKind

# Tracking status string -> implicit FeedbackKind. SAVED (and anything unknown)
# produces no signal: saving a job is not yet an outcome.
_STATUS_TO_KIND: dict[str, FeedbackKind] = {
    "applied": FeedbackKind.APPLIED,
    "interviewing": FeedbackKind.INTERVIEWING,
    "offered": FeedbackKind.OFFERED,
    "accepted": FeedbackKind.ACCEPTED,
    "rejected": FeedbackKind.REJECTED,
}


def status_to_feedback_kind(status: str) -> FeedbackKind | None:
    return _STATUS_TO_KIND.get(status)

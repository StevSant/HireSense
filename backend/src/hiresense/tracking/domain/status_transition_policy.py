from __future__ import annotations

from hiresense.tracking.domain.models import ApplicationStatus


class InvalidStatusTransitionError(ValueError):
    """Raised when an application status change is not allowed by the state
    machine. Subclasses ValueError so existing generic handling still works,
    but the API layer catches it specifically to answer 409 rather than 404."""


# Allowed forward/lateral moves. Two hard rules shape this graph, chosen so the
# illogical transitions flagged in issue #167 (a terminal state or a later stage
# reverting to SAVED, "re-applying" out of a closed application) are rejected
# while every legitimate move the app relies on still passes:
#   1. ACCEPTED and REJECTED are terminal — no transitions leave them.
#   2. Nothing transitions back to SAVED once it has left.
# Corrections within the active pipeline stay open (e.g. INTERVIEWING -> APPLIED,
# which the applied_at-preservation flow depends on). A no-op self-transition is
# always allowed and never reaches this map (the service short-circuits it).
_ALLOWED_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.SAVED: frozenset(
        {
            ApplicationStatus.APPLIED,
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.OFFERED,
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
        }
    ),
    ApplicationStatus.APPLIED: frozenset(
        {
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.OFFERED,
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
        }
    ),
    ApplicationStatus.INTERVIEWING: frozenset(
        {
            ApplicationStatus.APPLIED,
            ApplicationStatus.OFFERED,
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
        }
    ),
    ApplicationStatus.OFFERED: frozenset(
        {
            ApplicationStatus.APPLIED,
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
        }
    ),
    ApplicationStatus.ACCEPTED: frozenset(),
    ApplicationStatus.REJECTED: frozenset(),
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """Whether moving an application from `from_status` to `to_status` is allowed.

    A no-op (same status) is always valid. An unrecognized source status is
    treated permissively (True) so legacy or hand-set data is never wedged.
    """
    if from_status == to_status:
        return True
    try:
        source = ApplicationStatus(from_status)
        target = ApplicationStatus(to_status)
    except ValueError:
        return True
    return target in _ALLOWED_TRANSITIONS[source]


def ensure_valid_transition(from_status: str, to_status: str) -> None:
    """Raise InvalidStatusTransitionError when the transition is not allowed."""
    if not is_valid_transition(from_status, to_status):
        raise InvalidStatusTransitionError(
            f"Cannot change status from '{from_status}' to '{to_status}'"
        )

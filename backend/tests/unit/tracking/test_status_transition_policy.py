from __future__ import annotations

import pytest

from hiresense.tracking.domain import (
    InvalidStatusTransitionError,
    ensure_valid_transition,
    is_valid_transition,
)
from hiresense.tracking.domain.models import ApplicationStatus

SAVED = ApplicationStatus.SAVED.value
APPLIED = ApplicationStatus.APPLIED.value
INTERVIEWING = ApplicationStatus.INTERVIEWING.value
OFFERED = ApplicationStatus.OFFERED.value
ACCEPTED = ApplicationStatus.ACCEPTED.value
REJECTED = ApplicationStatus.REJECTED.value


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (SAVED, APPLIED),
        (SAVED, INTERVIEWING),  # skip-ahead, used by tests/seed flows
        (SAVED, OFFERED),
        (APPLIED, INTERVIEWING),
        (INTERVIEWING, APPLIED),  # correction within pipeline (applied_at flow)
        (APPLIED, REJECTED),
        (INTERVIEWING, OFFERED),
        (OFFERED, ACCEPTED),
        (APPLIED, APPLIED),  # no-op
        (REJECTED, REJECTED),  # no-op even on a terminal state
    ],
)
def test_valid_transitions_allowed(from_status: str, to_status: str) -> None:
    assert is_valid_transition(from_status, to_status) is True


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (REJECTED, SAVED),
        (OFFERED, SAVED),
        (APPLIED, SAVED),
        (REJECTED, APPLIED),  # re-applying out of a terminal state
        (ACCEPTED, INTERVIEWING),
        (REJECTED, OFFERED),
    ],
)
def test_invalid_transitions_rejected(from_status: str, to_status: str) -> None:
    assert is_valid_transition(from_status, to_status) is False


def test_unknown_source_status_is_permissive() -> None:
    assert is_valid_transition("legacy_unknown", APPLIED) is True


def test_ensure_valid_transition_raises_on_invalid() -> None:
    with pytest.raises(InvalidStatusTransitionError):
        ensure_valid_transition(REJECTED, SAVED)


def test_ensure_valid_transition_passes_on_valid() -> None:
    ensure_valid_transition(SAVED, APPLIED)  # does not raise

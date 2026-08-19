from __future__ import annotations

from enum import Enum


class JobClosureReason(str, Enum):
    """Why a job was closed — the signal the closure decision rested on.

    PROBE_404 and CLOSED_MARKER are kept apart deliberately: they are the two
    distinct ways the URL-probe sweep decides a listing is gone, and telling
    them apart is what makes "is the sweep over-closing?" answerable.
    """

    PROBE_404 = "probe_404"
    CLOSED_MARKER = "closed_marker"
    DEAD_END_REDIRECT = "dead_end_redirect"
    EXPIRY = "expiry"
    SNAPSHOT_DISAPPEARANCE = "snapshot_disappearance"

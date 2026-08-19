from __future__ import annotations

from enum import Enum

from hiresense.ingestion.domain.job_closure_reason import JobClosureReason


class Verdict(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


def classify_listing(*, status_code: int, body: str, markers: list[str]) -> Verdict:
    """Map an HTTP probe result to a lifecycle verdict.

    404/410 -> CLOSED. 200 + a closed-marker phrase in the body -> CLOSED
    (covers listings that stay live but say "no longer accepting"). 200 plain
    -> OPEN. Anything else (5xx, redirects, or a timeout the caller surfaces as
    a non-200/404/410 code) -> UNKNOWN; UNKNOWN never closes a job.
    """
    if status_code in (404, 410):
        return Verdict.CLOSED
    if status_code == 200:
        low = body.lower()
        if any(m.lower() in low for m in markers):
            return Verdict.CLOSED
        return Verdict.OPEN
    return Verdict.UNKNOWN


def closure_reason(status_code: int) -> JobClosureReason:
    """Which signal a CLOSED verdict rested on.

    Only meaningful when classify_listing already returned CLOSED. 404/410 is
    the listing being gone; anything else reaching here is a 200 page whose
    body matched a closed-marker phrase.
    """
    if status_code in (404, 410):
        return JobClosureReason.PROBE_404
    return JobClosureReason.CLOSED_MARKER

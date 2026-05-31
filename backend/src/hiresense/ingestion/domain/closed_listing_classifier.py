from __future__ import annotations

from enum import Enum


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

from __future__ import annotations

import uuid as uuid_mod
from typing import Any

from hiresense.inbox.domain.classification import EmailClassification
from hiresense.inbox.domain.email_signal_kind import EmailSignalKind
from hiresense.tracking.domain.models import ApplicationStatus

_KIND_TO_STATUS = {
    EmailSignalKind.REJECTION: ApplicationStatus.REJECTED,
    EmailSignalKind.INTERVIEW: ApplicationStatus.INTERVIEWING,
    EmailSignalKind.OFFER: ApplicationStatus.OFFERED,
}

_ACTIVE_STATUSES = {ApplicationStatus.APPLIED.value, ApplicationStatus.INTERVIEWING.value}


def _normalize(company: str | None) -> str:
    return "".join(ch for ch in (company or "").lower() if ch.isalnum() or ch.isspace()).strip()


def _company_matches(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return a in b or b in a


class ApplicationMatcher:
    """Matches a classified email to one active tracked application by company.
    Returns (application_id, proposed_status_value) or (None, None) when there's
    no signal-bearing kind, confidence is too low, or the company match is absent
    or ambiguous."""

    def __init__(self, min_confidence: float) -> None:
        self._min_confidence = min_confidence

    def match(
        self, classification: EmailClassification, active_apps: list[Any]
    ) -> tuple[uuid_mod.UUID | None, str | None]:
        status = _KIND_TO_STATUS.get(classification.kind)
        if status is None or classification.confidence < self._min_confidence:
            return None, None
        target = _normalize(classification.company)
        if not target:
            return None, None
        matches = [
            app
            for app in active_apps
            if app.status in _ACTIVE_STATUSES and _company_matches(target, _normalize(app.company))
        ]
        if len(matches) != 1:
            return None, None  # no match or ambiguous
        return matches[0].id, status.value

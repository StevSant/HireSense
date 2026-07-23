"""Conservative extraction of explicit work-authorization statements from job text."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel


class WorkAuthorizationFacts(BaseModel):
    """Facts stated by a job posting; ``None`` means the posting is silent."""

    requires_existing_work_authorization: bool | None = None
    visa_sponsorship_available: bool | None = None


_NO_SPONSORSHIP = re.compile(
    r"\b(?:no|without) (?:visa )?sponsorship\b"
    r"|\b(?:visa )?sponsorship (?:is )?(?:not available|not offered|unavailable)\b"
    r"|\b(?:we|the company) (?:do(?:es)? not|cannot|can't|will not) sponsor\b",
    re.IGNORECASE,
)
_SPONSORSHIP_AVAILABLE = re.compile(
    r"\b(?:visa )?sponsorship (?:is )?(?:available|offered|provided)\b"
    r"|\bwe (?:offer|provide|can sponsor) (?:visa )?sponsorship\b",
    re.IGNORECASE,
)
_EXISTING_AUTHORIZATION_REQUIRED = re.compile(
    r"\b(?:must|require(?:s|d)?|need(?:s|ed)? to) (?:be )?(?:currently |legally )?"
    r"authorized to work\b"
    r"|\b(?:must|require(?:s|d)?|need(?:s|ed)? to) have (?:current |existing )?"
    r"work authorization\b"
    r"|\bauthorized to work\b.{0,80}\bwithout (?:visa )?sponsorship\b",
    re.IGNORECASE,
)


def extract_work_authorization_facts(description: str | None) -> WorkAuthorizationFacts:
    """Return only facts explicitly stated in a posting's description.

    The patterns deliberately avoid inferring policy from a location, a job
    title, or generic mentions of visas. A detected statement wins only when
    it is unambiguous; absent facts remain ``None`` for matching to treat as
    unknown.
    """
    text = " ".join((description or "").split())
    no_sponsorship = bool(_NO_SPONSORSHIP.search(text))
    sponsorship_available = (
        False if no_sponsorship else True if _SPONSORSHIP_AVAILABLE.search(text) else None
    )
    return WorkAuthorizationFacts(
        requires_existing_work_authorization=(
            True if _EXISTING_AUTHORIZATION_REQUIRED.search(text) else None
        ),
        visa_sponsorship_available=sponsorship_available,
    )


def add_work_authorization_facts(normalized: dict[str, Any]) -> dict[str, Any]:
    """Enrich normalizer output without replacing source-provided boolean facts."""
    facts = extract_work_authorization_facts(str(normalized.get("description") or ""))
    result = dict(normalized)
    for field, inferred in facts.model_dump().items():
        if not isinstance(result.get(field), bool):
            result[field] = inferred
    return result

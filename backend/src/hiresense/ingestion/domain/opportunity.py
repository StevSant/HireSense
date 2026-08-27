"""Derived opportunity and international-pathway classifications.

These classifications intentionally use only facts already present on a
normalized posting. They are presentation and filtering helpers, not claims
that an employer will sponsor a particular visa or that a candidate is
eligible to work in a country.
"""

from __future__ import annotations

import enum

from hiresense.ingestion.domain.seniority import SeniorityLevel, detect_seniority


class OpportunityType(str, enum.Enum):
    INTERNSHIP = "internship"
    ENTRY_LEVEL = "entry_level"
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    OTHER = "other"
    UNKNOWN = "unknown"


class InternationalPathway(str, enum.Enum):
    INTERNATIONAL = "international"
    VISA_SPONSORSHIP = "visa_sponsorship"
    WORLDWIDE_REMOTE = "worldwide_remote"


_KNOWN_EMPLOYMENT_TYPES = {
    "full_time": OpportunityType.FULL_TIME,
    "part_time": OpportunityType.PART_TIME,
    "contract": OpportunityType.CONTRACT,
    "temporary": OpportunityType.TEMPORARY,
    "other": OpportunityType.OTHER,
}


def classify_opportunity_type(
    employment_type: str | None,
    title: str,
    description: str = "",
) -> OpportunityType:
    """Return a stable, user-facing role type for a normalized posting."""
    normalized = (employment_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    seniority = detect_seniority(title, description)
    # Internship wins over a source's generic full_time value because an
    # internship title is the more useful distinction for the candidate.
    if normalized in {"intern", "internship"} or seniority is SeniorityLevel.INTERN:
        return OpportunityType.INTERNSHIP
    if normalized in _KNOWN_EMPLOYMENT_TYPES:
        return _KNOWN_EMPLOYMENT_TYPES[normalized]
    if seniority is SeniorityLevel.JUNIOR:
        return OpportunityType.ENTRY_LEVEL
    return OpportunityType.UNKNOWN


def is_worldwide_remote(
    remote_modality: str | None,
    countries: list[str] | None,
    location: str = "",
) -> bool:
    """Recognize remote roles without an explicit country restriction."""
    if remote_modality == "remote" and not countries:
        return True
    haystack = (location or "").lower()
    return remote_modality == "remote" and any(
        marker in haystack for marker in ("worldwide", "anywhere", "global")
    )


def international_pathways(
    *,
    visa_sponsorship_available: bool | None,
    remote_modality: str | None,
    countries: list[str] | None,
    location: str = "",
) -> list[str]:
    """Return explicit international routes supported by the posting."""
    pathways: list[str] = []
    if visa_sponsorship_available is True:
        pathways.append(InternationalPathway.VISA_SPONSORSHIP.value)
    if is_worldwide_remote(remote_modality, countries, location):
        pathways.append(InternationalPathway.WORLDWIDE_REMOTE.value)
    if pathways:
        pathways.insert(0, InternationalPathway.INTERNATIONAL.value)
    return pathways

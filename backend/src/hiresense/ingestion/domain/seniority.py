"""Heuristic seniority detection for job postings.

Inputs are raw title + description text; outputs are a coarse level
(`SeniorityLevel`) and an optional minimum-years-experience integer when the
posting states one (e.g. "5+ years of experience").

The detector is intentionally conservative: it only emits a label when the
text contains a clear signal. This lets the filter UI surface "Unknown" as
an explicit bucket rather than silently mis-bucketing ambiguous postings.
"""
from __future__ import annotations

import enum
import re


class SeniorityLevel(str, enum.Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    UNKNOWN = "unknown"


_TITLE_RULES: tuple[tuple[re.Pattern[str], SeniorityLevel], ...] = (
    # Order matters: 'staff engineer' is a lead-level role even though it
    # contains no obvious seniority word, so match before SENIOR / MID.
    (re.compile(r"\b(intern|internship|trainee|practicante|becari[oa])\b", re.I), SeniorityLevel.INTERN),
    (re.compile(r"\b(principal|staff|distinguished|fellow|head\s+of|director|vp|chief|cto|cpo)\b", re.I), SeniorityLevel.LEAD),
    (re.compile(r"\b(lead|líder|team\s+lead|tech\s+lead)\b", re.I), SeniorityLevel.LEAD),
    (re.compile(r"\b(senior|sr\.?|snr|principal|sénior|s[eé]nior)\b", re.I), SeniorityLevel.SENIOR),
    (re.compile(r"\b(junior|jr\.?|entry[\s-]?level|graduate|grad\s+(role|hire)|trainee|associate|asociado)\b", re.I), SeniorityLevel.JUNIOR),
    (re.compile(r"\b(mid[\s-]?level|intermediate|mid\s+(developer|engineer))\b", re.I), SeniorityLevel.MID),
)

_YEARS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(\d{1,2})\s*[-–]\s*\d{1,2}\s+(?:years?|yrs?|años)\b", re.I),
    re.compile(r"(\d{1,2})\s+to\s+\d{1,2}\s+(?:years?|yrs?|años)\b", re.I),
    re.compile(r"(\d{1,2})\s*\+\s*(?:years?|yrs?|años)", re.I),
    re.compile(r"(?:minimum|at\s+least|m[ií]nimo\s+de?)\s+(\d{1,2})\s+(?:years?|yrs?|años)", re.I),
    re.compile(r"(\d{1,2})\s+(?:years?|yrs?|años)\s+(?:of\s+)?(?:[a-z]+\s+)?experience", re.I),
)


def extract_min_years(text: str) -> int | None:
    """Best-effort extraction of the *minimum* years-of-experience asked for.

    Returns the smallest plausible year value found (capped at 30) or None if
    nothing matches. Multiple patterns are tried; the lowest wins so e.g.
    "3-7 years" yields 3.
    """
    if not text:
        return None
    candidates: list[int] = []
    for pattern in _YEARS_PATTERNS:
        for match in pattern.finditer(text):
            try:
                years = int(match.group(1))
            except (ValueError, IndexError):
                continue
            if 0 < years <= 30:
                candidates.append(years)
    return min(candidates) if candidates else None


def detect_seniority(title: str, description: str = "") -> SeniorityLevel:
    """Classify the posting from its title (primary) + body fallback."""
    if title:
        for pattern, level in _TITLE_RULES:
            if pattern.search(title):
                return level
    if description:
        # Description fallback uses the same rules but with an extra guard:
        # we don't want a body mention of "lead the team" to flag a senior
        # role as LEAD, so only intern / junior / senior keywords win here.
        body_only = (SeniorityLevel.INTERN, SeniorityLevel.JUNIOR, SeniorityLevel.SENIOR)
        for pattern, level in _TITLE_RULES:
            if level in body_only and pattern.search(description):
                return level
        years = extract_min_years(description)
        if years is not None:
            if years <= 1:
                return SeniorityLevel.JUNIOR
            if years <= 4:
                return SeniorityLevel.MID
            if years <= 7:
                return SeniorityLevel.SENIOR
            return SeniorityLevel.LEAD
    return SeniorityLevel.UNKNOWN

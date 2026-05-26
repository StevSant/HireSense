from __future__ import annotations

from hiresense.ingestion.domain.seniority import (
    SeniorityLevel,
    detect_seniority,
    extract_min_years,
)


def test_intern_title() -> None:
    assert detect_seniority("AI Agent Developer Intern") == SeniorityLevel.INTERN


def test_senior_abbreviation() -> None:
    assert detect_seniority("Sr. Backend Engineer") == SeniorityLevel.SENIOR


def test_principal_is_lead() -> None:
    assert detect_seniority("Principal Engineer (Data & Platform)") == SeniorityLevel.LEAD


def test_unknown_when_title_lacks_signal() -> None:
    # No clear seniority cue → UNKNOWN unless body adds one.
    assert detect_seniority("Software Engineer") == SeniorityLevel.UNKNOWN


def test_falls_back_to_years_in_description() -> None:
    # Body explicitly asks for 5+ years → SENIOR by the years rule.
    title = "Software Engineer"
    body = "We are looking for someone with 5+ years of experience in Python."
    assert detect_seniority(title, body) == SeniorityLevel.SENIOR


def test_years_pattern_minimum_at_least() -> None:
    assert extract_min_years("at least 3 years of experience") == 3


def test_years_pattern_range_picks_low_end() -> None:
    assert extract_min_years("3-7 years of relevant experience") == 3


def test_extract_returns_none_when_silent() -> None:
    assert extract_min_years("We use Python and FastAPI.") is None

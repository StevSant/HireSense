from hiresense.ingestion.domain.candidate_level import infer_candidate_level
from hiresense.ingestion.domain.seniority import SeniorityLevel


def test_intern_keyword_wins():
    assert infer_candidate_level("AI Agent Developer Intern, 2026") is SeniorityLevel.INTERN


def test_junior_keyword():
    assert infer_candidate_level("Junior backend developer") is SeniorityLevel.JUNIOR


def test_senior_keyword():
    assert infer_candidate_level("Senior software engineer at BigCo") is SeniorityLevel.SENIOR


def test_years_only_maps_to_band():
    # No explicit level word; 5 years → senior band (<= 7).
    assert infer_candidate_level("Backend engineer with 5+ years of experience") is (
        SeniorityLevel.SENIOR
    )


def test_no_signal_is_unknown_not_mid():
    # The whole point: never silently assume mid-level.
    assert infer_candidate_level("Passionate builder who loves shipping products") is (
        SeniorityLevel.UNKNOWN
    )


def test_empty_is_unknown():
    assert infer_candidate_level("") is SeniorityLevel.UNKNOWN

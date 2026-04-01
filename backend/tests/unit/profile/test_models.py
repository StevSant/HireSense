from hiresense.profile.domain.models import CandidateProfile, CVSection


def test_cv_section_creation() -> None:
    section = CVSection(
        name="TECHNICAL SKILLS",
        content="Python, FastAPI, Django, PostgreSQL",
    )
    assert section.name == "TECHNICAL SKILLS"
    assert "Python" in section.content


def test_candidate_profile_creation() -> None:
    sections = [
        CVSection(name="SUMMARY", content="Backend engineer..."),
        CVSection(name="TECHNICAL SKILLS", content="Python, FastAPI"),
    ]
    profile = CandidateProfile(
        id="profile-1",
        name="Bryan Menoscal",
        email="bryan@example.com",
        sections=sections,
        raw_tex="\\documentclass{article}...",
        language="en",
    )
    assert profile.name == "Bryan Menoscal"
    assert len(profile.sections) == 2


def test_candidate_profile_skills_from_sections() -> None:
    profile = CandidateProfile(
        id="profile-1",
        name="Bryan Menoscal",
        email="bryan@example.com",
        sections=[],
        raw_tex="",
        language="en",
        skills=["python", "fastapi", "django"],
    )
    assert "fastapi" in profile.skills


def test_candidate_profile_optional_fields() -> None:
    profile = CandidateProfile(
        id="profile-1",
        name="Test User",
        sections=[],
        raw_tex="",
        language="en",
    )
    assert profile.email is None
    assert profile.phone is None
    assert profile.location is None
    assert profile.skills == []
    assert profile.embedding is None

from __future__ import annotations

from hiresense.profile.domain.models import CandidateProfile, CVSection
from hiresense.profile.domain.profile_language_view import ProfileLanguageView
from hiresense.profile.domain.services import ProfileService


class FakeLatexParser:
    pass


class FakeSkillExtractor:
    pass


def _make_service_with_in_memory_profiles(*profiles: CandidateProfile) -> ProfileService:
    service = ProfileService(
        parser=FakeLatexParser(),
        skill_extractor=FakeSkillExtractor(),
        repository=None,
    )
    for p in profiles:
        service._profiles[p.id] = p
    return service


def _make_profile(profile_id: str, language: str, summary_text: str, skills: list[str], raw_tex: str = "TEX") -> CandidateProfile:
    return CandidateProfile(
        id=profile_id,
        name="Bryan",
        sections=[CVSection(name="summary", content=summary_text)],
        raw_tex=raw_tex,
        language=language,
        skills=skills,
    )


def test_returns_view_for_existing_language() -> None:
    service = _make_service_with_in_memory_profiles(
        _make_profile("1", "en", "English summary text.", ["python", "fastapi"], raw_tex=r"\documentclass{article}"),
    )

    view = service.get_for_language("en")

    assert view is not None
    assert isinstance(view, ProfileLanguageView)
    assert view.language == "en"
    assert "English summary text" in view.summary
    assert view.skills == ["python", "fastapi"]
    assert view.raw_tex == r"\documentclass{article}"


def test_returns_none_for_missing_language() -> None:
    service = _make_service_with_in_memory_profiles(
        _make_profile("1", "en", "x", []),
    )

    assert service.get_for_language("es") is None


def test_summary_joins_multiple_sections() -> None:
    profile = CandidateProfile(
        id="2",
        name="Bryan",
        sections=[
            CVSection(name="summary", content="First paragraph."),
            CVSection(name="experience", content="Second paragraph."),
        ],
        raw_tex="",
        language="en",
        skills=[],
    )
    service = _make_service_with_in_memory_profiles(profile)

    view = service.get_for_language("en")

    assert view is not None
    assert "First paragraph." in view.summary
    assert "Second paragraph." in view.summary


def test_returns_latest_when_multiple_for_same_language() -> None:
    older = _make_profile("a", "en", "older", ["old"])
    newer = _make_profile("b", "en", "newer", ["new"])
    service = _make_service_with_in_memory_profiles(older, newer)

    view = service.get_for_language("en")

    assert view is not None
    assert view.skills == ["new"]

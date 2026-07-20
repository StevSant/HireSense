from __future__ import annotations

from hiresense.profile.domain.contact_info import ContactInfo
from hiresense.profile.domain.models import CandidateProfile, CVSection
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


def _make_profile(
    profile_id: str,
    language: str,
    *,
    name: str,
    email: str | None,
    phone: str | None,
) -> CandidateProfile:
    return CandidateProfile(
        id=profile_id,
        name=name,
        email=email,
        phone=phone,
        sections=[CVSection(name="summary", content="text")],
        raw_tex="TEX",
        language=language,
    )


def test_returns_contact_info_for_existing_language() -> None:
    service = _make_service_with_in_memory_profiles(
        _make_profile("1", "en", name="Bryan", email="bryan@example.com", phone="+1-555-0100"),
    )

    contact = service.get_contact_info("en")

    assert contact == ContactInfo(name="Bryan", email="bryan@example.com", phone="+1-555-0100")


def test_returns_none_when_no_profile_for_language() -> None:
    service = _make_service_with_in_memory_profiles(
        _make_profile("1", "en", name="Bryan", email=None, phone=None),
    )

    assert service.get_contact_info("es") is None


def test_uses_latest_profile_for_language() -> None:
    older = _make_profile("a", "en", name="Old Name", email="old@example.com", phone=None)
    newer = _make_profile("b", "en", name="New Name", email="new@example.com", phone=None)
    service = _make_service_with_in_memory_profiles(older, newer)

    contact = service.get_contact_info("en")

    assert contact is not None
    assert contact.name == "New Name"
    assert contact.email == "new@example.com"

from __future__ import annotations

import uuid

import pytest

from hiresense.applications.domain.apply_service import (
    PLACEHOLDER_CANDIDATE_NAME,
    ApplyService,
)
from hiresense.applications.domain.models import ApplicationCoverLetter
from hiresense.profile.domain.contact_info import ContactInfo


class FakeLatexCompiler:
    """Captures the render_cover_letter_tex kwargs and returns canned PDF bytes."""

    def __init__(self) -> None:
        self.render_kwargs: dict | None = None

    def render_cover_letter_tex(self, **kwargs) -> str:
        self.render_kwargs = kwargs
        return "TEX"

    async def compile_to_pdf(self, tex: str) -> bytes:
        return b"%PDF"


class FakeRepo:
    def __init__(self, letter: ApplicationCoverLetter) -> None:
        self._letter = letter

    def get_latest_cover_letter(self, application_id):
        return self._letter


class FakeTracked:
    company = "Fieldguide"


class FakeTrackingService:
    def get(self, _):
        return FakeTracked()


class FakeProfileService:
    """Exposes only the public contact port — no private latest-profile lookup."""

    def __init__(self, contact: ContactInfo | None) -> None:
        self._contact = contact
        self.asked_language: str | None = None

    def get_contact_info(self, language: str) -> ContactInfo | None:
        self.asked_language = language
        return self._contact


def _make_service(contact: ContactInfo | None) -> tuple[ApplyService, FakeLatexCompiler]:
    latex = FakeLatexCompiler()
    letter = ApplicationCoverLetter(
        id=uuid.uuid4(),
        application_id=uuid.uuid4(),
        match_id=None,
        body="Dear team,",
        tone="professional",
    )
    service = ApplyService(
        repository=FakeRepo(letter),  # type: ignore[arg-type]
        cover_letter_generator=None,  # type: ignore[arg-type]
        latex_compiler=latex,  # type: ignore[arg-type]
        profile_service=FakeProfileService(contact),
        tracking_service=FakeTrackingService(),
    )
    return service, latex


@pytest.mark.asyncio
async def test_cover_letter_pdf_uses_public_contact_info() -> None:
    contact = ContactInfo(name="Bryan", email="bryan@example.com", phone="+1-555-0100")
    service, latex = _make_service(contact)

    await service.compile_cover_letter_pdf(uuid.uuid4())

    assert latex.render_kwargs is not None
    assert latex.render_kwargs["candidate_name"] == "Bryan"
    assert latex.render_kwargs["candidate_email"] == "bryan@example.com"
    assert latex.render_kwargs["candidate_phone"] == "+1-555-0100"


@pytest.mark.asyncio
async def test_cover_letter_pdf_falls_back_to_placeholder_when_no_profile() -> None:
    service, latex = _make_service(None)

    await service.compile_cover_letter_pdf(uuid.uuid4())

    assert latex.render_kwargs is not None
    assert latex.render_kwargs["candidate_name"] == PLACEHOLDER_CANDIDATE_NAME
    assert latex.render_kwargs["candidate_email"] is None
    assert latex.render_kwargs["candidate_phone"] is None

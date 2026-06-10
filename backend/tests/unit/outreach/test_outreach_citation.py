"""Tests: portfolio citation integration in outreach generation.

Covers:
- OutreachMessageGenerator.generate appends portfolio section + mention-instruction
  when portfolio_section is given; prompt is unchanged (no "portfolio" text) when omitted.
- OutreachService.generate calls citation_for with the correct job_text / application_id /
  language and forwards the returned section to the generator.
- The existing suite (test_outreach_service.py) implicitly covers the default-None
  portfolio_citation path — no test here is needed for that case.
"""
from __future__ import annotations

import uuid as uuid_mod

import pytest

from hiresense.outreach.domain.message_generator import OutreachMessageGenerator
from hiresense.outreach.domain.outreach_service import OutreachService


# ---------------------------------------------------------------------------
# Fakes shared across both test groups
# ---------------------------------------------------------------------------


class _FakeLLM:
    def __init__(self, text: str = "drafted") -> None:
        self.calls: list[tuple[str, str]] = []
        self.text = text

    async def complete(self, prompt: str, system: str) -> str:
        self.calls.append((prompt, system))
        return self.text


class _App:
    def __init__(self, app_id: uuid_mod.UUID) -> None:
        self.id = app_id
        self.company = "Acme"
        self.title = "Backend Engineer"
        self.status = "applied"
        self.notes = "We build fast APIs for fintech clients."
        self.url = None


class _Tracking:
    def __init__(self, app: _App) -> None:
        self._app = app

    def get(self, app_id: uuid_mod.UUID) -> _App:
        if app_id != self._app.id:
            raise ValueError("not found")
        return self._app


class _Profile:
    async def get_current_profile(self, language: str | None = None):
        return type("P", (), {"name": "Bryan"})()

    def get_for_language(self, language: str | None):
        return type("V", (), {"skills": ["python"], "summary": "dev"})()


class _Research:
    def get(self, company: str):
        return None


class _CapturingGen:
    """Records the kwargs it was called with."""

    def __init__(self) -> None:
        self.kwargs: dict | None = None

    async def generate(self, **kwargs) -> str:
        self.kwargs = kwargs
        return "outreach body"


class _Repo:
    def add(self, event):
        return event

    def list_for(self, app_id):
        return []

    def latest_per_application(self):
        return []


class _FakeCitationService:
    """Mimics PortfolioCitationService.citation_for."""

    def __init__(self, result: str | None = "See my widget at https://example.com") -> None:
        self.result = result
        self.calls: list[dict] = []

    async def citation_for(
        self,
        *,
        job_skills: list[str],
        job_text: str,
        application_id: str,
        language: str | None,
    ) -> str | None:
        self.calls.append(
            {"job_skills": job_skills, "job_text": job_text,
             "application_id": application_id, "language": language}
        )
        return self.result


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------


def _gen(llm):
    return OutreachMessageGenerator(llm=llm)


_COMMON_KWARGS = dict(
    company="Acme",
    title="Backend Engineer",
    job_description="Build APIs for fintech",
    candidate_name="Bryan",
    candidate_summary="FastAPI dev",
    candidate_skills=["python"],
    company_research=None,
    contact_name=None,
    style_guide="BE CONCISE",
    channel=None,
    max_chars=500,
)


@pytest.mark.asyncio
async def test_generator_includes_portfolio_section_and_instruction():
    llm = _FakeLLM()
    section = "Portfolio: built a job-board scraper (https://example.com)"
    await _gen(llm).generate(**_COMMON_KWARGS, portfolio_section=section)
    prompt, _ = llm.calls[0]
    assert section in prompt
    assert "Mention at most ONE of these projects" in prompt
    assert "portfolio link" in prompt.lower()


@pytest.mark.asyncio
async def test_generator_omits_portfolio_when_none():
    llm = _FakeLLM()
    await _gen(llm).generate(**_COMMON_KWARGS, portfolio_section=None)
    prompt, _ = llm.calls[0]
    assert "portfolio" not in prompt.lower()


@pytest.mark.asyncio
async def test_generator_omits_portfolio_when_empty_string():
    llm = _FakeLLM()
    await _gen(llm).generate(**_COMMON_KWARGS, portfolio_section="")
    prompt, _ = llm.calls[0]
    assert "portfolio" not in prompt.lower()


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


def _svc(app: _App, gen, citation=None) -> OutreachService:
    return OutreachService(
        tracking_service=_Tracking(app),
        profile_service=_Profile(),
        research_service=_Research(),
        generator=gen,
        repo=_Repo(),
        style_guide_path="does/not/exist.md",
        followup_cadence_days=7,
        max_chars=500,
        language="en",
        portfolio_citation=citation,
    )


@pytest.mark.asyncio
async def test_service_passes_portfolio_section_to_generator():
    app_id = uuid_mod.uuid4()
    app = _App(app_id)
    citation_svc = _FakeCitationService("Portfolio: https://example.com")
    gen = _CapturingGen()
    svc = _svc(app, gen, citation=citation_svc)

    await svc.generate(app_id)

    assert gen.kwargs is not None
    assert gen.kwargs["portfolio_section"] == "Portfolio: https://example.com"


@pytest.mark.asyncio
async def test_service_calls_citation_with_correct_args():
    app_id = uuid_mod.uuid4()
    app = _App(app_id)
    citation_svc = _FakeCitationService("some section")
    gen = _CapturingGen()
    svc = _svc(app, gen, citation=citation_svc)

    await svc.generate(app_id)

    assert len(citation_svc.calls) == 1
    call = citation_svc.calls[0]
    # job_text must equal what the service passes as job_description to the generator
    assert call["job_text"] == gen.kwargs["job_description"]
    assert call["application_id"] == str(app_id)
    assert call["language"] == "en"


@pytest.mark.asyncio
async def test_service_passes_none_section_when_citation_returns_none():
    app_id = uuid_mod.uuid4()
    app = _App(app_id)
    citation_svc = _FakeCitationService(result=None)
    gen = _CapturingGen()
    svc = _svc(app, gen, citation=citation_svc)

    await svc.generate(app_id)

    assert gen.kwargs["portfolio_section"] is None


@pytest.mark.asyncio
async def test_service_with_no_citation_passes_none_section():
    """Mirrors the default-None path covered implicitly by the existing suite."""
    app_id = uuid_mod.uuid4()
    app = _App(app_id)
    gen = _CapturingGen()
    svc = _svc(app, gen, citation=None)

    await svc.generate(app_id)

    assert gen.kwargs["portfolio_section"] is None

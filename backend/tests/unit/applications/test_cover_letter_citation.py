from __future__ import annotations

import uuid

import pytest

from hiresense.applications.domain.cover_letter_generator import (
    USER_PROMPT_TEMPLATE,
    CoverLetterGenerator,
)
from hiresense.applications.domain.apply_service import ApplyService
from hiresense.applications.domain.models import (
    ApplicationCoverLetter,
    ApplicationJobSnapshot,
    JobSnapshotSource,
)
from hiresense.kernel.prompt_boundary import PromptBoundary


# ---------------------------------------------------------------------------
# Shared fakes (adapted from existing test files in this package)
# ---------------------------------------------------------------------------


class FakeLLM:
    """Captures the prompt sent and returns a canned response."""

    def __init__(self, response: str = "COVER_LETTER") -> None:
        self.response = response
        self.last_prompt: str | None = None

    async def complete(self, prompt: str, *, system: str = "") -> str:
        self.last_prompt = prompt
        return self.response


class FakeCitationService:
    """Simulates PortfolioCitationService; records call kwargs and returns text."""

    def __init__(self, text: str | None = "Portfolio: https://example.com/portfolio") -> None:
        self.text = text
        self.last_kwargs: dict | None = None

    async def citation_for(
        self, *, job_skills, job_text, application_id, language=None
    ) -> str | None:
        self.last_kwargs = {
            "job_skills": job_skills,
            "job_text": job_text,
            "application_id": application_id,
            "language": language,
        }
        return self.text


class FakeRepo:
    def __init__(self, snapshot: ApplicationJobSnapshot | None = None) -> None:
        self._snapshot = snapshot
        self._covers: list[ApplicationCoverLetter] = []

    def get_snapshot(self, application_id):
        return self._snapshot

    def get_latest_match(self, application_id):
        return None

    def create_cover_letter(self, row: ApplicationCoverLetter) -> ApplicationCoverLetter:
        row.id = row.id or uuid.uuid4()
        self._covers.append(row)
        return row


class FakeTracked:
    title = "Software Engineer"
    company = "Fieldguide"


class FakeTrackingService:
    def get(self, _):
        return FakeTracked()


class FakeProfile:
    language = "en"
    summary = "Experienced engineer."
    skills = ["python", "fastapi"]
    raw_tex = ""


class FakeProfileService:
    def get_for_language(self, language: str) -> FakeProfile:
        return FakeProfile()


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------

_COMMON_KWARGS = dict(
    title="Software Engineer",
    company="Acme",
    description="Build microservices.",
    candidate_summary="5 years Python.",
    candidate_skills=["python"],
    required_skills=["python", "docker"],
    pros=["strong python"],
    missing_skills=["k8s"],
    tone="professional",
)


@pytest.mark.asyncio
async def test_generator_appends_portfolio_section_and_weave_instruction() -> None:
    """When portfolio_section is provided, it appears in the prompt followed by the weave instruction."""
    llm = FakeLLM()
    gen = CoverLetterGenerator(llm=llm)
    portfolio_text = "Portfolio: https://example.com/projects"

    await gen.generate(**_COMMON_KWARGS, portfolio_section=portfolio_text)

    assert llm.last_prompt is not None
    assert portfolio_text in llm.last_prompt
    assert "Weave at most two of these projects" in llm.last_prompt
    assert "include it verbatim exactly once" in llm.last_prompt


@pytest.mark.asyncio
async def test_generator_portfolio_section_inserted_before_constraints() -> None:
    """Portfolio block must appear BEFORE the Constraints: section in the prompt."""
    llm = FakeLLM()
    gen = CoverLetterGenerator(llm=llm)
    portfolio_text = "Portfolio: https://example.com/projects"

    await gen.generate(**_COMMON_KWARGS, portfolio_section=portfolio_text)

    prompt = llm.last_prompt
    assert prompt is not None
    portfolio_pos = prompt.index(portfolio_text)
    constraints_pos = prompt.index("Constraints:")
    assert portfolio_pos < constraints_pos, (
        "Portfolio section should appear before Constraints: block"
    )


@pytest.mark.asyncio
async def test_generator_splices_at_template_constraints_not_description_decoy() -> None:
    """A job description containing a literal "Constraints:\\n" must NOT hijack
    the splice point — the portfolio block anchors to the template's trailing
    Constraints section (last occurrence), not the description's decoy."""
    llm = FakeLLM()
    gen = CoverLetterGenerator(llm=llm)
    portfolio_text = "Relevant portfolio: https://example.com/projects"
    kwargs = dict(_COMMON_KWARGS)
    kwargs["description"] = "Build microservices.\nConstraints:\n- must pass a background check\n"

    await gen.generate(**kwargs, portfolio_section=portfolio_text)

    prompt = llm.last_prompt
    assert prompt is not None
    # Description's fake Constraints occurrence comes BEFORE the portfolio block.
    assert prompt.rindex("Relevant portfolio") > prompt.index("Constraints:")
    # The block sits immediately before the LAST (template) Constraints section.
    marker = "Constraints:\n"
    last_constraints = prompt.rindex(marker)
    portfolio_block_end = prompt.rindex("verbatim exactly once.") + len("verbatim exactly once.")
    assert prompt[portfolio_block_end:last_constraints] == "\n\n"
    # And the template's real Constraints body follows it intact.
    assert prompt[last_constraints:].startswith("Constraints:\n- Tone:")


@pytest.mark.asyncio
async def test_generator_prompt_byte_identical_when_no_portfolio() -> None:
    """When portfolio_section is omitted (None), the prompt must equal USER_PROMPT_TEMPLATE.format(...)."""
    llm = FakeLLM()
    gen = CoverLetterGenerator(llm=llm)

    await gen.generate(**_COMMON_KWARGS)  # no portfolio_section

    expected = USER_PROMPT_TEMPLATE.format(
        title=_COMMON_KWARGS["title"],
        company=_COMMON_KWARGS["company"],
        description=PromptBoundary.untrusted_job_content(
            _COMMON_KWARGS["description"], max_chars=12000
        ),
        candidate_summary=_COMMON_KWARGS["candidate_summary"],
        candidate_skills=", ".join(_COMMON_KWARGS["candidate_skills"]),
        required_skills=", ".join(_COMMON_KWARGS["required_skills"]),
        pros=", ".join(_COMMON_KWARGS["pros"]),
        missing_skills=", ".join(_COMMON_KWARGS["missing_skills"]),
        tone=_COMMON_KWARGS["tone"],
    )
    assert llm.last_prompt == expected


@pytest.mark.asyncio
async def test_generator_no_portfolio_mention_when_omitted() -> None:
    """No 'portfolio' word (case-insensitive) should appear when portfolio_section is None."""
    llm = FakeLLM()
    gen = CoverLetterGenerator(llm=llm)

    await gen.generate(**_COMMON_KWARGS)

    assert "portfolio" not in (llm.last_prompt or "").lower()


# ---------------------------------------------------------------------------
# ApplyService tests
# ---------------------------------------------------------------------------


def _make_apply_service(
    snapshot: ApplicationJobSnapshot,
    *,
    citation_service=None,
    llm_response: str = "Generated cover letter body.",
) -> tuple[ApplyService, FakeLLM]:
    llm = FakeLLM(response=llm_response)
    generator = CoverLetterGenerator(llm=llm)
    service = ApplyService(
        repository=FakeRepo(snapshot=snapshot),
        cover_letter_generator=generator,
        latex_compiler=None,  # type: ignore[arg-type]
        profile_service=FakeProfileService(),
        tracking_service=FakeTrackingService(),
        portfolio_citation=citation_service,
    )
    return service, llm


@pytest.mark.asyncio
async def test_apply_service_passes_snapshot_fields_to_citation_service() -> None:
    """ApplyService forwards snapshot.required_skills, .description, application_id, cv_language."""
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="We need Python and FastAPI expertise.",
        required_skills=["python", "fastapi"],
        source=JobSnapshotSource.MANUAL.value,
    )
    citation = FakeCitationService(text="Portfolio: https://example.com")
    service, _ = _make_apply_service(snap, citation_service=citation)

    await service.generate_cover_letter(app_id, cv_language="en", tone="professional")

    assert citation.last_kwargs is not None
    assert citation.last_kwargs["job_skills"] == ["python", "fastapi"]
    assert citation.last_kwargs["job_text"] == "We need Python and FastAPI expertise."
    assert citation.last_kwargs["application_id"] == str(app_id)
    assert citation.last_kwargs["language"] == "en"


@pytest.mark.asyncio
async def test_apply_service_forwards_citation_text_to_generator() -> None:
    """The text returned by citation_for ends up in the LLM prompt."""
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="Build distributed systems.",
        required_skills=["go", "kafka"],
        source=JobSnapshotSource.MANUAL.value,
    )
    portfolio_text = "Portfolio: https://example.com/work"
    citation = FakeCitationService(text=portfolio_text)
    service, llm = _make_apply_service(snap, citation_service=citation)

    await service.generate_cover_letter(app_id, cv_language="en")

    assert llm.last_prompt is not None
    assert portfolio_text in llm.last_prompt
    assert "Weave at most two of these projects" in llm.last_prompt


@pytest.mark.asyncio
async def test_apply_service_none_citation_result_no_portfolio_in_prompt() -> None:
    """When citation_for returns None, the prompt contains no portfolio mention."""
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="Frontend work.",
        required_skills=["react"],
        source=JobSnapshotSource.MANUAL.value,
    )
    citation = FakeCitationService(text=None)  # returns None
    service, llm = _make_apply_service(snap, citation_service=citation)

    await service.generate_cover_letter(app_id, cv_language="fr")

    assert "portfolio" not in (llm.last_prompt or "").lower()


@pytest.mark.asyncio
async def test_apply_service_no_portfolio_citation_behaves_as_before() -> None:
    """With portfolio_citation=None (default), the prompt is byte-identical to no-portfolio path."""
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="Backend work.",
        required_skills=["python"],
        source=JobSnapshotSource.MANUAL.value,
    )
    service, llm = _make_apply_service(snap, citation_service=None)

    await service.generate_cover_letter(app_id, cv_language="en")

    assert "portfolio" not in (llm.last_prompt or "").lower()
    assert "Weave at most two" not in (llm.last_prompt or "")

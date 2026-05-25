"""Tests for CoverLetterGenerator template-injection behavior."""
from __future__ import annotations

import pytest

from hiresense.applications.domain.cover_letter_generator import CoverLetterGenerator


class CapturingLLM:
    """Captures the prompt for assertions."""

    def __init__(self) -> None:
        self.last_prompt: str = ""
        self.last_system: str | None = None

    async def complete(self, prompt: str, system: str | None = None) -> str:
        self.last_prompt = prompt
        self.last_system = system
        return "Generated cover letter body."


def _common_args() -> dict[str, object]:
    return {
        "title": "Senior Backend Engineer",
        "company": "Acme",
        "description": "Build distributed systems.",
        "candidate_summary": "10 years backend.",
        "candidate_skills": ["python", "postgres"],
        "required_skills": ["python", "k8s"],
        "pros": ["deep python"],
        "missing_skills": ["k8s"],
    }


@pytest.mark.asyncio
async def test_generator_omits_template_section_when_template_body_is_none() -> None:
    llm = CapturingLLM()
    gen = CoverLetterGenerator(llm=llm)
    await gen.generate(**_common_args())
    assert "Stylistic reference" not in llm.last_prompt


@pytest.mark.asyncio
async def test_generator_includes_template_body_when_provided() -> None:
    llm = CapturingLLM()
    gen = CoverLetterGenerator(llm=llm)
    template = "Best regards,\nBryan"
    await gen.generate(**_common_args(), template_body=template)
    assert "Stylistic reference" in llm.last_prompt
    assert template in llm.last_prompt
    # Ordering: the per-job context comes first; the template hint is appended at the end.
    job_idx = llm.last_prompt.index("Job Description")
    tmpl_idx = llm.last_prompt.index("Stylistic reference")
    assert job_idx < tmpl_idx


@pytest.mark.asyncio
async def test_generator_ignores_whitespace_only_template() -> None:
    llm = CapturingLLM()
    gen = CoverLetterGenerator(llm=llm)
    await gen.generate(**_common_args(), template_body="   \n  ")
    assert "Stylistic reference" not in llm.last_prompt


@pytest.mark.asyncio
async def test_generator_raises_when_llm_not_configured() -> None:
    gen = CoverLetterGenerator(llm=None)
    with pytest.raises(RuntimeError, match="LLM not configured"):
        await gen.generate(**_common_args(), template_body="x")

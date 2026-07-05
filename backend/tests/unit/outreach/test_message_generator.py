import pytest

from hiresense.outreach.domain.message_generator import (
    OutreachMessageGenerator,
    OutreachUnavailableError,
)


class _FakeLLM:
    def __init__(self, text="  Hi Sam, ...  "):
        self.text = text
        self.calls = []

    async def complete(self, prompt, system):
        self.calls.append((prompt, system))
        return self.text


def _gen(llm):
    return OutreachMessageGenerator(llm=llm)


@pytest.mark.asyncio
async def test_generates_stripped_body_with_style_and_research():
    llm = _FakeLLM()
    out = await _gen(llm).generate(
        company="Acme",
        title="Backend Engineer",
        job_description="Build APIs",
        candidate_name="Bryan",
        candidate_summary="FastAPI dev",
        candidate_skills=["python"],
        company_research="Culture: remote-first",
        contact_name="Sam",
        style_guide="BE CONCISE",
        channel="linkedin",
        max_chars=500,
    )
    assert out == "Hi Sam, ..."
    prompt, system = llm.calls[0]
    assert "BE CONCISE" in prompt and "Bryan" in prompt and "Backend Engineer" in prompt
    assert "Culture: remote-first" in prompt and "Sam" in prompt


@pytest.mark.asyncio
async def test_omits_research_when_none():
    llm = _FakeLLM()
    await _gen(llm).generate(
        company="Acme",
        title="BE",
        job_description="x",
        candidate_name="Bryan",
        candidate_summary="s",
        candidate_skills=[],
        company_research=None,
        contact_name=None,
        style_guide="SG",
        channel=None,
        max_chars=500,
    )
    prompt, _ = llm.calls[0]
    assert "Company research" not in prompt  # the research block is omitted


@pytest.mark.asyncio
async def test_raises_when_no_llm():
    with pytest.raises(OutreachUnavailableError):
        await _gen(None).generate(
            company="Acme",
            title="BE",
            job_description="x",
            candidate_name="B",
            candidate_summary="s",
            candidate_skills=[],
            company_research=None,
            contact_name=None,
            style_guide="SG",
            channel=None,
            max_chars=500,
        )

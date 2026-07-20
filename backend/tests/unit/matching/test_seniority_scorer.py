import pytest

from hiresense.matching.domain.scorers.seniority_scorer import SeniorityScorer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


JOB = {
    "title": "Senior Backend Engineer",
    "company": "Acme Corp",
    "description": "We need a 4-6 year experienced backend engineer.",
    "location": "Remote",
    "salary_range": "$120k-$150k",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
}


@pytest.mark.asyncio
async def test_seniority_scorer_returns_result() -> None:
    llm = FakeLLM('{"score": 0.85, "rationale": "Good seniority match"}')
    scorer = SeniorityScorer(llm=llm, weight=15)
    result = await scorer.score(JOB)
    assert result.score == 0.85
    assert result.rationale == "Good seniority match"
    assert result.dimension == "seniority_fit"
    assert result.weight == 15


@pytest.mark.asyncio
async def test_seniority_scorer_includes_job_info_in_prompt() -> None:
    llm = FakeLLM('{"score": 0.75, "rationale": "Decent fit"}')
    scorer = SeniorityScorer(llm=llm, weight=15)
    await scorer.score(JOB)
    assert "Senior Backend Engineer" in llm.last_prompt
    assert "Acme Corp" in llm.last_prompt
    assert "4-6 year" in llm.last_prompt


@pytest.mark.asyncio
async def test_seniority_scorer_no_llm_fallback() -> None:
    scorer = SeniorityScorer(llm=None, weight=15)
    result = await scorer.score(JOB)
    assert result.score == 0.5
    assert "not configured" in result.rationale.lower()
    assert result.dimension == "seniority_fit"


@pytest.mark.asyncio
async def test_seniority_scorer_dimension_name() -> None:
    scorer = SeniorityScorer(llm=None, weight=15)
    assert scorer.dimension_name == "seniority_fit"


@pytest.mark.asyncio
async def test_seniority_scorer_weight() -> None:
    scorer = SeniorityScorer(llm=None, weight=20)
    assert scorer.weight == 20


@pytest.mark.asyncio
async def test_seniority_scorer_truncates_long_description() -> None:
    llm = FakeLLM('{"score": 0.5, "rationale": "ok"}')
    scorer = SeniorityScorer(llm=llm, weight=15)
    job = {**JOB, "description": "x" * 50_000}
    await scorer.score(job)
    assert len(llm.last_prompt) < 10_000

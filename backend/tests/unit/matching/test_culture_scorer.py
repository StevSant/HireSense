import pytest

from hiresense.matching.domain.scorers.culture_scorer import CultureScorer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


JOB = {
    "title": "Backend Engineer",
    "company": "Remote-First Corp",
    "description": "We are fully remote, async-first, with great work-life balance.",
    "location": "Remote (Worldwide)",
    "salary_range": "$120k-$150k",
    "skills": ["Python", "FastAPI"],
}


@pytest.mark.asyncio
async def test_culture_scorer_returns_result() -> None:
    llm = FakeLLM('{"score": 0.95, "rationale": "Remote-first aligns perfectly"}')
    scorer = CultureScorer(llm=llm, weight=15)
    result = await scorer.score(JOB)
    assert result.score == 0.95
    assert result.rationale == "Remote-first aligns perfectly"
    assert result.dimension == "culture_fit"
    assert result.weight == 15


@pytest.mark.asyncio
async def test_culture_scorer_includes_location_in_prompt() -> None:
    llm = FakeLLM('{"score": 0.8, "rationale": "Good culture"}')
    scorer = CultureScorer(llm=llm, weight=15)
    await scorer.score(JOB)
    assert "Remote (Worldwide)" in llm.last_prompt
    assert "Remote-First Corp" in llm.last_prompt


@pytest.mark.asyncio
async def test_culture_scorer_includes_description_in_prompt() -> None:
    llm = FakeLLM('{"score": 0.75, "rationale": "OK culture"}')
    scorer = CultureScorer(llm=llm, weight=15)
    await scorer.score(JOB)
    assert "work-life balance" in llm.last_prompt


@pytest.mark.asyncio
async def test_culture_scorer_no_llm_fallback() -> None:
    scorer = CultureScorer(llm=None, weight=15)
    result = await scorer.score(JOB)
    assert result.score == 0.5
    assert "not configured" in result.rationale.lower()
    assert result.dimension == "culture_fit"


@pytest.mark.asyncio
async def test_culture_scorer_dimension_name() -> None:
    scorer = CultureScorer(llm=None, weight=15)
    assert scorer.dimension_name == "culture_fit"


@pytest.mark.asyncio
async def test_culture_scorer_truncates_long_description() -> None:
    llm = FakeLLM('{"score": 0.5, "rationale": "ok"}')
    scorer = CultureScorer(llm=llm, weight=15)
    job = {**JOB, "description": "x" * 50_000}
    await scorer.score(job)
    assert len(llm.last_prompt) < 10_000

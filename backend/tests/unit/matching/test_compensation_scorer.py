import pytest

from hiresense.matching.domain.scorers.compensation_scorer import CompensationScorer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


JOB = {
    "title": "Backend Engineer",
    "company": "Tech Startup",
    "description": "Build APIs and services.",
    "location": "San Francisco, CA",
    "salary_range": "$130k-$160k",
    "skills": ["Python", "FastAPI"],
}

JOB_NO_SALARY = {
    "title": "Backend Engineer",
    "company": "Tech Startup",
    "description": "Build APIs and services.",
    "location": "San Francisco, CA",
    "salary_range": "",
    "skills": ["Python", "FastAPI"],
}


@pytest.mark.asyncio
async def test_compensation_scorer_returns_result() -> None:
    llm = FakeLLM('{"score": 0.9, "rationale": "Competitive pay"}')
    scorer = CompensationScorer(llm=llm, weight=20)
    result = await scorer.score(JOB)
    assert result.score == 0.9
    assert result.rationale == "Competitive pay"
    assert result.dimension == "compensation"
    assert result.weight == 20


@pytest.mark.asyncio
async def test_compensation_scorer_includes_salary_in_prompt() -> None:
    llm = FakeLLM('{"score": 0.8, "rationale": "Good range"}')
    scorer = CompensationScorer(llm=llm, weight=20)
    await scorer.score(JOB)
    assert "$130k-$160k" in llm.last_prompt
    assert "San Francisco" in llm.last_prompt


@pytest.mark.asyncio
async def test_compensation_scorer_handles_missing_salary() -> None:
    llm = FakeLLM('{"score": 0.5, "rationale": "No salary info"}')
    scorer = CompensationScorer(llm=llm, weight=20)
    await scorer.score(JOB_NO_SALARY)
    assert "Not specified" in llm.last_prompt


@pytest.mark.asyncio
async def test_compensation_scorer_no_llm_fallback() -> None:
    scorer = CompensationScorer(llm=None, weight=20)
    result = await scorer.score(JOB)
    assert result.score == 0.5
    assert "not configured" in result.rationale.lower()
    assert result.dimension == "compensation"


@pytest.mark.asyncio
async def test_compensation_scorer_dimension_name() -> None:
    scorer = CompensationScorer(llm=None, weight=20)
    assert scorer.dimension_name == "compensation"


@pytest.mark.asyncio
async def test_compensation_scorer_truncates_long_description() -> None:
    llm = FakeLLM('{"score": 0.5, "rationale": "ok"}')
    scorer = CompensationScorer(llm=llm, weight=20)
    job = {**JOB, "description": "x" * 50_000}
    await scorer.score(job)
    assert len(llm.last_prompt) < 10_000

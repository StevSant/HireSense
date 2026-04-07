import pytest

from hiresense.matching.domain.scorers.growth_scorer import GrowthScorer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


JOB = {
    "title": "ML Engineer",
    "company": "AI Company",
    "description": "Work on cutting-edge ML models with mentorship from senior researchers.",
    "location": "Remote",
    "salary_range": "$140k-$170k",
    "skills": ["Python", "PyTorch", "LangChain"],
}


@pytest.mark.asyncio
async def test_growth_scorer_returns_result() -> None:
    llm = FakeLLM('{"score": 0.9, "rationale": "Excellent learning opportunities"}')
    scorer = GrowthScorer(llm=llm, weight=15)
    result = await scorer.score(JOB)
    assert result.score == 0.9
    assert result.rationale == "Excellent learning opportunities"
    assert result.dimension == "growth_potential"
    assert result.weight == 15


@pytest.mark.asyncio
async def test_growth_scorer_includes_job_info_in_prompt() -> None:
    llm = FakeLLM('{"score": 0.85, "rationale": "Great stack"}')
    scorer = GrowthScorer(llm=llm, weight=15)
    await scorer.score(JOB)
    assert "ML Engineer" in llm.last_prompt
    assert "AI Company" in llm.last_prompt
    assert "PyTorch" in llm.last_prompt


@pytest.mark.asyncio
async def test_growth_scorer_no_llm_fallback() -> None:
    scorer = GrowthScorer(llm=None, weight=15)
    result = await scorer.score(JOB)
    assert result.score == 0.5
    assert "not configured" in result.rationale.lower()
    assert result.dimension == "growth_potential"


@pytest.mark.asyncio
async def test_growth_scorer_dimension_name() -> None:
    scorer = GrowthScorer(llm=None, weight=15)
    assert scorer.dimension_name == "growth_potential"


@pytest.mark.asyncio
async def test_growth_scorer_weight() -> None:
    scorer = GrowthScorer(llm=None, weight=25)
    assert scorer.weight == 25

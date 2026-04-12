import pytest

from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        return self._response


class ConcreteLLMScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "test_dimension"

    @property
    def weight(self) -> int:
        return 10

    def _build_prompt(self, job, profile=None) -> str:
        return f"Evaluate: {job.get('title', '')}"

    def _output_schema(self):
        return DimensionResult


@pytest.mark.asyncio
async def test_llm_scorer_parses_json_response() -> None:
    llm = FakeLLM('{"score": 0.85, "rationale": "Great fit"}')
    scorer = ConcreteLLMScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.85
    assert result.rationale == "Great fit"
    assert result.dimension == "test_dimension"
    assert result.weight == 10


@pytest.mark.asyncio
async def test_llm_scorer_handles_malformed_json() -> None:
    llm = FakeLLM("This is not JSON but score is 0.7 probably")
    scorer = ConcreteLLMScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.5


@pytest.mark.asyncio
async def test_llm_scorer_handles_complete_garbage() -> None:
    llm = FakeLLM("I cannot evaluate this")
    scorer = ConcreteLLMScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.5


@pytest.mark.asyncio
async def test_llm_scorer_handles_llm_exception() -> None:
    class FailingLLM:
        async def complete(self, prompt, *, system="", model=""):
            raise RuntimeError("API timeout")

    scorer = ConcreteLLMScorer(llm=FailingLLM(), weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.5
    assert "API timeout" in result.rationale


@pytest.mark.asyncio
async def test_llm_scorer_handles_none_llm() -> None:
    scorer = ConcreteLLMScorer(llm=None, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.5
    assert "not configured" in result.rationale.lower()


@pytest.mark.asyncio
async def test_llm_scorer_clamps_score_above_one() -> None:
    llm = FakeLLM('{"score": 1.5, "rationale": "Off the charts"}')
    scorer = ConcreteLLMScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 1.0


@pytest.mark.asyncio
async def test_llm_scorer_extracts_json_from_markdown() -> None:
    llm = FakeLLM('Here is my analysis:\n```json\n{"score": 0.6, "rationale": "Decent"}\n```')
    scorer = ConcreteLLMScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.6
    assert result.rationale == "Decent"

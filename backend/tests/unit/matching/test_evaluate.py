import pytest
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.services import MatchingOrchestrator


class FakeScorer:
    def __init__(self, dimension, score, weight):
        self._dimension = dimension
        self._score = score
        self._weight = weight

    @property
    def dimension_name(self): return self._dimension

    @property
    def weight(self): return self._weight

    async def score(self, job, profile=None):
        return DimensionResult(dimension=self._dimension, score=self._score, rationale=f"Score for {self._dimension}", weight=self._weight)


class FakeEventBus:
    async def publish(self, event): pass


@pytest.mark.asyncio
async def test_evaluate_returns_composite_score():
    scorers = [FakeScorer("dim_a", 0.8, 60), FakeScorer("dim_b", 0.4, 40)]
    o = MatchingOrchestrator(llm=None, event_bus=FakeEventBus())
    result = await o.evaluate(job={"title": "SWE", "company": "Acme", "description": ""}, dimension_scorers=scorers)
    assert abs(result.composite_score - 0.64) < 0.01
    assert result.job_title == "SWE"
    assert len(result.dimensions) == 2


@pytest.mark.asyncio
async def test_evaluate_handles_scorer_exception():
    class FailingScorer:
        dimension_name = "failing"
        weight = 50

        async def score(self, job, profile=None): raise RuntimeError("boom")

    scorers = [FakeScorer("good", 0.8, 50), FailingScorer()]
    o = MatchingOrchestrator(llm=None, event_bus=FakeEventBus())
    result = await o.evaluate(job={"title": "SWE", "company": "Acme", "description": ""}, dimension_scorers=scorers)
    assert len(result.dimensions) == 2
    failing = [d for d in result.dimensions if d.dimension == "failing"][0]
    assert failing.score == 0.5


@pytest.mark.asyncio
async def test_evaluate_all_dimensions():
    scorers = [FakeScorer(f"dim_{i}", 0.5, 10) for i in range(10)]
    o = MatchingOrchestrator(llm=None, event_bus=FakeEventBus())
    result = await o.evaluate(job={"title": "SWE", "company": "Acme", "description": ""}, dimension_scorers=scorers)
    assert len(result.dimensions) == 10
    assert result.composite_score == 0.5

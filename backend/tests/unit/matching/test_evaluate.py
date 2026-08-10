import logging

import pytest
from hiresense.shared.kernel.exceptions import UpstreamUnavailableError
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain import DimensionEvaluator


class FakeScorer:
    def __init__(self, dimension, score, weight):
        self._dimension = dimension
        self._score = score
        self._weight = weight

    @property
    def dimension_name(self):
        return self._dimension

    @property
    def weight(self):
        return self._weight

    async def score(self, job, profile=None):
        return DimensionResult(
            dimension=self._dimension,
            score=self._score,
            rationale=f"Score for {self._dimension}",
            weight=self._weight,
        )


class _FailingScorer:
    def __init__(self, dimension, weight):
        self.dimension_name = dimension
        self.weight = weight

    async def score(self, job, profile=None):
        raise RuntimeError("boom")


class FakeEventBus:
    async def publish(self, event):
        pass


@pytest.mark.asyncio
async def test_evaluate_returns_composite_score():
    scorers = [FakeScorer("dim_a", 0.8, 60), FakeScorer("dim_b", 0.4, 40)]
    o = DimensionEvaluator()
    result = await o.evaluate(
        job={"title": "SWE", "company": "Acme", "description": ""}, dimension_scorers=scorers
    )
    assert abs(result.composite_score - 0.64) < 0.01
    assert result.job_title == "SWE"
    assert len(result.dimensions) == 2


@pytest.mark.asyncio
async def test_evaluate_excludes_failed_dimension_instead_of_fabricating_a_score():
    """A failed scorer used to be reported as score=0.5 at full weight, so the
    composite was part invention. It must be dropped, not made up."""
    scorers = [FakeScorer("good", 0.8, 50), _FailingScorer("failing", 50)]
    o = DimensionEvaluator()
    result = await o.evaluate(
        job={"title": "SWE", "company": "Acme", "description": ""}, dimension_scorers=scorers
    )
    assert [d.dimension for d in result.dimensions] == ["good"]
    # Composite is renormalized over what actually scored — not (0.8+0.5)/2.
    assert result.composite_score == 0.8


@pytest.mark.asyncio
async def test_evaluate_logs_the_failed_dimension(caplog):
    scorers = [FakeScorer("good", 0.8, 50), _FailingScorer("failing", 50)]
    o = DimensionEvaluator()
    with caplog.at_level(logging.ERROR, logger="hiresense.matching.domain.services"):
        await o.evaluate(
            job={"title": "SWE", "company": "Acme", "description": ""}, dimension_scorers=scorers
        )
    assert any("failing" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_evaluate_raises_when_every_dimension_fails():
    """With nothing scored, the composite would silently fall back to a
    plausible 0.5 built from no data at all."""
    scorers = [_FailingScorer("a", 50), _FailingScorer("b", 50)]
    o = DimensionEvaluator()
    with pytest.raises(UpstreamUnavailableError):
        await o.evaluate(
            job={"title": "SWE", "company": "Acme", "description": ""}, dimension_scorers=scorers
        )


@pytest.mark.asyncio
async def test_evaluate_with_no_scorers_wired_is_unchanged():
    """ "No scorers configured" is not a failure — the bare-orchestrator path
    must keep returning the neutral composite it always did."""
    o = DimensionEvaluator()
    result = await o.evaluate(
        job={"title": "SWE", "company": "Acme", "description": ""}, dimension_scorers=[]
    )
    assert result.dimensions == []
    assert result.composite_score == 0.5


@pytest.mark.asyncio
async def test_evaluate_all_dimensions():
    scorers = [FakeScorer(f"dim_{i}", 0.5, 10) for i in range(10)]
    o = DimensionEvaluator()
    result = await o.evaluate(
        job={"title": "SWE", "company": "Acme", "description": ""}, dimension_scorers=scorers
    )
    assert len(result.dimensions) == 10
    assert result.composite_score == 0.5

from __future__ import annotations

import pytest

from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.services import MatchingOrchestrator


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
            rationale="",
            weight=self._weight,
        )


class FakeEventBus:
    async def publish(self, event):
        pass


class FakePreference:
    def __init__(self, overrides):
        self._overrides = overrides

    def weight_overrides(self):
        return self._overrides


_JOB = {"title": "SWE", "company": "Acme", "description": ""}


@pytest.mark.asyncio
async def test_no_preference_port_is_unchanged():
    scorers = [FakeScorer("a", 0.8, 60), FakeScorer("b", 0.4, 40)]
    o = MatchingOrchestrator(llm=None, event_bus=FakeEventBus())
    result = await o.evaluate(job=_JOB, dimension_scorers=scorers)
    # 0.8*60 + 0.4*40 = 64 / 100 = 0.64
    assert abs(result.composite_score - 0.64) < 1e-9


@pytest.mark.asyncio
async def test_empty_overrides_is_byte_identical():
    scorers = [FakeScorer("a", 0.8, 60), FakeScorer("b", 0.4, 40)]
    baseline = await MatchingOrchestrator(llm=None, event_bus=FakeEventBus()).evaluate(
        job=_JOB, dimension_scorers=scorers
    )
    with_pref = await MatchingOrchestrator(
        llm=None, event_bus=FakeEventBus(), preference=FakePreference({})
    ).evaluate(job=_JOB, dimension_scorers=scorers)
    assert with_pref.composite_score == baseline.composite_score


@pytest.mark.asyncio
async def test_override_shifts_composite():
    # Boost the high-scoring dimension's weight; composite should rise.
    scorers = [FakeScorer("a", 0.8, 60), FakeScorer("b", 0.4, 40)]
    o = MatchingOrchestrator(
        llm=None, event_bus=FakeEventBus(), preference=FakePreference({"a": 20})
    )
    result = await o.evaluate(job=_JOB, dimension_scorers=scorers)
    # 0.8*80 + 0.4*40 = 80 / 120 = 0.6667 (composite is rounded to 4 dp)
    assert abs(result.composite_score - (80.0 / 120.0)) < 1e-4
    assert result.composite_score > 0.64


@pytest.mark.asyncio
async def test_negative_override_lowers_composite():
    scorers = [FakeScorer("a", 0.8, 60), FakeScorer("b", 0.4, 40)]
    o = MatchingOrchestrator(
        llm=None, event_bus=FakeEventBus(), preference=FakePreference({"a": -30})
    )
    result = await o.evaluate(job=_JOB, dimension_scorers=scorers)
    # 0.8*30 + 0.4*40 = 40 / 70 = 0.5714 (composite is rounded to 4 dp)
    assert abs(result.composite_score - (40.0 / 70.0)) < 1e-4
    assert result.composite_score < 0.64


@pytest.mark.asyncio
async def test_override_floors_effective_weight_at_zero():
    scorers = [FakeScorer("a", 0.8, 10), FakeScorer("b", 0.4, 40)]
    # delta -30 would make 'a' negative; floored to 0 so it drops out entirely.
    o = MatchingOrchestrator(
        llm=None, event_bus=FakeEventBus(), preference=FakePreference({"a": -30})
    )
    result = await o.evaluate(job=_JOB, dimension_scorers=scorers)
    # only 'b' contributes: 0.4*40 / 40 = 0.4
    assert abs(result.composite_score - 0.4) < 1e-9


@pytest.mark.asyncio
async def test_preference_lookup_failure_falls_back_to_base():
    class Boom:
        def weight_overrides(self):
            raise RuntimeError("boom")

    scorers = [FakeScorer("a", 0.8, 60), FakeScorer("b", 0.4, 40)]
    o = MatchingOrchestrator(llm=None, event_bus=FakeEventBus(), preference=Boom())
    result = await o.evaluate(job=_JOB, dimension_scorers=scorers)
    assert abs(result.composite_score - 0.64) < 1e-9

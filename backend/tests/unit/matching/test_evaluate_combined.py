from __future__ import annotations

import pytest

from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.services import MatchingOrchestrator

_JOB = {"title": "SWE", "company": "Acme", "description": ""}


class FakeEventBus:
    async def publish(self, event):
        pass


class FakeScorer:
    def __init__(self, dimension, score, weight):
        self._dimension = dimension
        self._score = score
        self._weight = weight
        self.calls = 0

    @property
    def dimension_name(self):
        return self._dimension

    @property
    def weight(self):
        return self._weight

    async def score(self, job, profile=None):
        self.calls += 1
        return DimensionResult(
            dimension=self._dimension, score=self._score, rationale="", weight=self._weight
        )


class StubCombinedScorer:
    """Fake CombinedDimensionScorer: returns whatever is configured."""

    def __init__(self, results=None, raises: Exception | None = None):
        self._results = results
        self._raises = raises
        self.calls = 0

    async def score_all(self, job, profile=None):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._results


def _dim(name, score):
    # weight=0 mimics the real CombinedDimensionScorer's placeholder weight —
    # the orchestrator must remap it from the wired per-dimension scorers.
    return DimensionResult(dimension=name, score=score, rationale="from combined", weight=0)


@pytest.mark.asyncio
async def test_combined_path_used_by_default_when_configured() -> None:
    fan_out_scorers = [FakeScorer("a", 0.1, 60), FakeScorer("b", 0.1, 40)]
    combined = StubCombinedScorer(results=[_dim("a", 0.8), _dim("b", 0.4)])
    o = MatchingOrchestrator(
        llm=None,
        event_bus=FakeEventBus(),
        dimension_scorers=fan_out_scorers,
        combined_scorer=combined,
    )
    result = await o.evaluate(job=_JOB)

    assert combined.calls == 1
    assert all(s.calls == 0 for s in fan_out_scorers)  # fan-out not invoked
    # 0.8*60 + 0.4*40 = 64 / 100 = 0.64
    assert abs(result.composite_score - 0.64) < 1e-9


@pytest.mark.asyncio
async def test_combined_result_gets_weights_from_wiring_not_llm() -> None:
    fan_out_scorers = [FakeScorer("a", 0.5, 70), FakeScorer("b", 0.5, 30)]
    combined = StubCombinedScorer(results=[_dim("a", 1.0), _dim("b", 0.0)])
    o = MatchingOrchestrator(
        llm=None,
        event_bus=FakeEventBus(),
        dimension_scorers=fan_out_scorers,
        combined_scorer=combined,
    )
    result = await o.evaluate(job=_JOB)

    weights = {d.dimension: d.weight for d in result.dimensions}
    assert weights == {"a": 70, "b": 30}


@pytest.mark.asyncio
async def test_malformed_combined_response_falls_back_to_fan_out() -> None:
    fan_out_scorers = [FakeScorer("a", 0.8, 60), FakeScorer("b", 0.4, 40)]
    combined = StubCombinedScorer(results=None)  # simulates unparseable response
    o = MatchingOrchestrator(
        llm=None,
        event_bus=FakeEventBus(),
        dimension_scorers=fan_out_scorers,
        combined_scorer=combined,
    )
    result = await o.evaluate(job=_JOB)

    assert combined.calls == 1
    assert all(s.calls == 1 for s in fan_out_scorers)  # fallback invoked
    assert abs(result.composite_score - 0.64) < 1e-9


@pytest.mark.asyncio
async def test_combined_scorer_exception_falls_back_to_fan_out() -> None:
    fan_out_scorers = [FakeScorer("a", 0.8, 60), FakeScorer("b", 0.4, 40)]
    combined = StubCombinedScorer(raises=RuntimeError("provider exploded"))
    o = MatchingOrchestrator(
        llm=None,
        event_bus=FakeEventBus(),
        dimension_scorers=fan_out_scorers,
        combined_scorer=combined,
    )
    result = await o.evaluate(job=_JOB)

    assert all(s.calls == 1 for s in fan_out_scorers)
    assert abs(result.composite_score - 0.64) < 1e-9


@pytest.mark.asyncio
async def test_no_combined_scorer_configured_uses_fan_out_directly() -> None:
    fan_out_scorers = [FakeScorer("a", 0.8, 60), FakeScorer("b", 0.4, 40)]
    o = MatchingOrchestrator(llm=None, event_bus=FakeEventBus(), dimension_scorers=fan_out_scorers)
    result = await o.evaluate(job=_JOB)

    assert all(s.calls == 1 for s in fan_out_scorers)
    assert abs(result.composite_score - 0.64) < 1e-9


@pytest.mark.asyncio
async def test_explicit_dimension_scorers_override_bypasses_combined_path() -> None:
    # Contract preserved for the preference-nudge flow: passing dimension_scorers
    # explicitly to evaluate() always uses the fan-out, even with a combined
    # scorer wired.
    override_scorers = [FakeScorer("x", 0.9, 50), FakeScorer("y", 0.1, 50)]
    combined = StubCombinedScorer(results=[_dim("x", 0.5), _dim("y", 0.5)])
    o = MatchingOrchestrator(
        llm=None,
        event_bus=FakeEventBus(),
        dimension_scorers=[FakeScorer("x", 0.0, 50), FakeScorer("y", 0.0, 50)],
        combined_scorer=combined,
    )
    result = await o.evaluate(job=_JOB, dimension_scorers=override_scorers)

    assert combined.calls == 0
    assert all(s.calls == 1 for s in override_scorers)
    # 0.9*50 + 0.1*50 = 50 / 100 = 0.5
    assert abs(result.composite_score - 0.5) < 1e-9


@pytest.mark.asyncio
async def test_combined_weight_overrides_apply_identically_to_fan_out() -> None:
    class FakePreference:
        def weight_overrides(self):
            return {"a": 20}

    fan_out_scorers = [FakeScorer("a", 0.8, 60), FakeScorer("b", 0.4, 40)]
    combined = StubCombinedScorer(results=[_dim("a", 0.8), _dim("b", 0.4)])
    o = MatchingOrchestrator(
        llm=None,
        event_bus=FakeEventBus(),
        dimension_scorers=fan_out_scorers,
        combined_scorer=combined,
        preference=FakePreference(),
    )
    result = await o.evaluate(job=_JOB)
    # 0.8*80 + 0.4*40 = 80 / 120 = 0.6667
    assert abs(result.composite_score - (80.0 / 120.0)) < 1e-4

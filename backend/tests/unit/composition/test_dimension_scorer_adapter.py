from __future__ import annotations

import pytest

from hiresense.composition.dimension_scorer_adapter import MatchingDimensionScorerAdapter
from hiresense.matching.domain import DimensionEvaluator
from hiresense.matching.domain.scorers.base import DimensionResult


class _FakeScorer:
    dimension_name = "culture"
    weight = 20

    async def score(self, job, profile) -> DimensionResult:
        return DimensionResult(dimension="culture", score=0.8, rationale="fits", weight=20)


class _FakeJobLookup:
    def __init__(self, job: object | None) -> None:
        self._job = job

    def get_job_by_id(self, job_id: str) -> object | None:
        return self._job


class _FakeProfileService:
    async def get_current_profile(self) -> dict:
        return {"skills": ["python"]}


def _adapter(evaluator: DimensionEvaluator, job: object | None = None):
    return MatchingDimensionScorerAdapter(
        evaluator=evaluator,
        job_lookup=_FakeJobLookup(job if job is not None else {"title": "SWE"}),
        profile_service=_FakeProfileService(),
    )


@pytest.mark.asyncio
async def test_returns_dimension_scores_when_scorers_are_wired() -> None:
    adapter = _adapter(DimensionEvaluator(dimension_scorers=[_FakeScorer()]))

    assert await adapter.score_dimensions("job-1") == {"culture": 0.8}


@pytest.mark.asyncio
async def test_returns_none_when_no_scorers_are_wired() -> None:
    # The guard this exercises used to be `getattr(orchestrator,
    # "_dimension_scorers", None)`. Renaming that private field would have made
    # the guard read None forever, silently disabling preference nudging while
    # every test still passed. It is now a public property on the evaluator.
    adapter = _adapter(DimensionEvaluator(dimension_scorers=[]))

    assert await adapter.score_dimensions("job-1") is None


@pytest.mark.asyncio
async def test_returns_none_when_the_job_is_unknown() -> None:
    adapter = MatchingDimensionScorerAdapter(
        evaluator=DimensionEvaluator(dimension_scorers=[_FakeScorer()]),
        job_lookup=_FakeJobLookup(None),
        profile_service=_FakeProfileService(),
    )

    assert await adapter.score_dimensions("missing") is None


@pytest.mark.asyncio
async def test_the_public_guard_tracks_the_wired_scorers() -> None:
    assert DimensionEvaluator(dimension_scorers=[_FakeScorer()]).has_dimension_scorers is True
    assert DimensionEvaluator(dimension_scorers=[]).has_dimension_scorers is False
    assert DimensionEvaluator().has_dimension_scorers is False

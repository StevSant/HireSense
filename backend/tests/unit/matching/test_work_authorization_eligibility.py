from __future__ import annotations

import pytest

from hiresense.matching.domain.eligibility import EligibilityStatus
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.services import MatchingOrchestrator
from hiresense.profile.domain import ApplyProfile, CandidateProfile, WorkAuthorizationStatus


class _EventBus:
    async def publish(self, event) -> None:
        pass


class _Scorer:
    dimension_name = "seniority_fit"
    weight = 100

    def __init__(self) -> None:
        self.calls = 0

    async def score(self, job, profile=None) -> DimensionResult:
        self.calls += 1
        return DimensionResult(
            dimension=self.dimension_name,
            score=0.9,
            rationale="Would be a strong fit",
            weight=self.weight,
        )


def _profile(status: WorkAuthorizationStatus) -> CandidateProfile:
    return CandidateProfile(
        id="candidate-1",
        name="Ada",
        apply_profile=ApplyProfile(work_authorization_status=status),
    )


@pytest.mark.asyncio
async def test_evaluate_skips_subjective_scorers_for_unsponsored_candidate() -> None:
    scorer = _Scorer()
    orchestrator = MatchingOrchestrator(llm=None, event_bus=_EventBus())

    result = await orchestrator.evaluate(
        job={
            "title": "Backend Engineer",
            "company": "Acme",
            "visa_sponsorship_available": False,
        },
        profile=_profile(WorkAuthorizationStatus.REQUIRES_SPONSORSHIP),
        dimension_scorers=[scorer],
    )

    assert result.eligibility.status is EligibilityStatus.INELIGIBLE
    assert result.composite_score == 0.0
    assert result.dimensions == []
    assert scorer.calls == 0


@pytest.mark.asyncio
async def test_evaluate_marks_authorized_candidate_eligible_when_job_requires_existing_authorization() -> (
    None
):
    scorer = _Scorer()
    orchestrator = MatchingOrchestrator(llm=None, event_bus=_EventBus())

    result = await orchestrator.evaluate(
        job={
            "title": "Backend Engineer",
            "company": "Acme",
            "requires_existing_work_authorization": True,
        },
        profile=_profile(WorkAuthorizationStatus.AUTHORIZED),
        dimension_scorers=[scorer],
    )

    assert result.eligibility.status is EligibilityStatus.ELIGIBLE
    assert scorer.calls == 1


@pytest.mark.asyncio
async def test_evaluate_leaves_missing_authorization_information_unknown() -> None:
    scorer = _Scorer()
    orchestrator = MatchingOrchestrator(llm=None, event_bus=_EventBus())

    result = await orchestrator.evaluate(
        job={"title": "Backend Engineer", "company": "Acme"},
        profile=_profile(WorkAuthorizationStatus.REQUIRES_SPONSORSHIP),
        dimension_scorers=[scorer],
    )

    assert result.eligibility.status is EligibilityStatus.UNKNOWN
    assert scorer.calls == 1

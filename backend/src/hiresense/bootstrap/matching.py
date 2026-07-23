from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.claims.domain import CandidateClaimService
from hiresense.matching.api.provider import MatchingProvider
from hiresense.matching.domain import BatchEvaluationService, MatchingOrchestrator
from hiresense.matching.domain.scorers import (
    ApplicationStrengthScorer,
    CombinedDimensionScorer,
    CompensationScorer,
    CultureScorer,
    GrowthScorer,
    InterviewReadinessScorer,
    SeniorityScorer,
)


@dataclass(frozen=True)
class MatchingBuild:
    provider: MatchingProvider
    orchestrator: MatchingOrchestrator


def build_matching(
    infra: SharedInfra,
    tracked: Callable[[str], Any],
    preference: Any | None = None,
    claim_service: CandidateClaimService | None = None,
) -> MatchingBuild:
    s = infra.settings
    job_char_limit = s.match_dimension_job_char_limit
    dimension_scorers = [
        SeniorityScorer(
            llm=tracked("seniority_scorer"),
            weight=s.weight_seniority,
            job_char_limit=job_char_limit,
        ),
        CompensationScorer(
            llm=tracked("compensation_scorer"),
            weight=s.weight_compensation,
            job_char_limit=job_char_limit,
        ),
        GrowthScorer(
            llm=tracked("growth_scorer"),
            weight=s.weight_growth,
            job_char_limit=job_char_limit,
        ),
        CultureScorer(
            llm=tracked("culture_scorer"),
            weight=s.weight_culture,
            job_char_limit=job_char_limit,
        ),
        ApplicationStrengthScorer(
            llm=tracked("application_strength_scorer"),
            weight=s.weight_application,
            job_char_limit=job_char_limit,
        ),
        InterviewReadinessScorer(
            llm=tracked("interview_readiness_scorer"),
            weight=s.weight_interview,
            job_char_limit=job_char_limit,
            claim_service=claim_service,
        ),
    ]
    # Default scoring path: all 6 dimensions in one LLM call. The individual
    # scorers above stay wired as the fallback when this fails to parse (and
    # as the explicit override target for the preference nudge flow).
    combined_scorer = CombinedDimensionScorer(
        llm=tracked("match_dimension_scorer"),
        job_char_limit=job_char_limit,
    )

    matching_orchestrator = MatchingOrchestrator(
        llm=tracked("matching_reasoning"),
        event_bus=infra.event_bus,
        dimension_scorers=dimension_scorers,
        embedding=infra.embedding,
        preference=preference,
        combined_scorer=combined_scorer,
    )
    batch_evaluation_service = BatchEvaluationService(
        orchestrator=matching_orchestrator,
        concurrency=s.batch_concurrency,
    )
    provider = MatchingProvider(
        orchestrator=matching_orchestrator,
        batch_evaluation_service=batch_evaluation_service,
    )
    return MatchingBuild(provider=provider, orchestrator=matching_orchestrator)

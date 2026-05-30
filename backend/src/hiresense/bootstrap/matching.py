from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.matching.api.provider import MatchingProvider
from hiresense.matching.domain import BatchEvaluationService, MatchingOrchestrator
from hiresense.matching.domain.scorers import (
    ApplicationStrengthScorer,
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


def build_matching(infra: SharedInfra, tracked: Callable[[str], Any]) -> MatchingBuild:
    s = infra.settings
    dimension_scorers = [
        SeniorityScorer(llm=tracked("seniority_scorer"), weight=s.weight_seniority),
        CompensationScorer(llm=tracked("compensation_scorer"), weight=s.weight_compensation),
        GrowthScorer(llm=tracked("growth_scorer"), weight=s.weight_growth),
        CultureScorer(llm=tracked("culture_scorer"), weight=s.weight_culture),
        ApplicationStrengthScorer(
            llm=tracked("application_strength_scorer"), weight=s.weight_application,
        ),
        InterviewReadinessScorer(
            llm=tracked("interview_readiness_scorer"), weight=s.weight_interview,
        ),
    ]

    matching_orchestrator = MatchingOrchestrator(
        llm=tracked("matching_reasoning"),
        event_bus=infra.event_bus,
        dimension_scorers=dimension_scorers,
        embedding=infra.embedding,
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

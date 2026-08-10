from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.claims.domain import CandidateClaimService
from hiresense.matching.api.provider import MatchingProvider
from hiresense.matching.domain import (
    BatchEvaluationService,
    DimensionEvaluator,
    MatchAnalyzer,
)
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
    dimension_evaluator: DimensionEvaluator
    match_analyzer: MatchAnalyzer


def _breakdown_weights(s: Any) -> dict[str, float]:
    """Normalize the four heuristic weight percentages into fractions.

    ScoreBreakdown.weighted_average multiplies by fractions, while the settings
    are whole percentages, so divide by their own total rather than a literal
    100 — that way a set which doesn't quite sum to 100 still produces a proper
    weighted average instead of silently scaling every score down.
    """
    percentages = {
        "semantic": float(s.weight_semantic),
        "skill": float(s.weight_skill_match),
        "experience": float(s.weight_experience),
        "language": float(s.weight_language),
    }
    total = sum(percentages.values())
    if total <= 0:
        # Degenerate config: fall back to ScoreBreakdown's own defaults rather
        # than dividing by zero or scoring every job 0.0.
        return {}
    return {key: value / total for key, value in percentages.items()}


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

    dimension_evaluator = DimensionEvaluator(
        dimension_scorers=dimension_scorers,
        preference=preference,
        combined_scorer=combined_scorer,
    )
    match_analyzer = MatchAnalyzer(
        llm=tracked("matching_reasoning"),
        event_bus=infra.event_bus,
        embedding=infra.embedding,
        breakdown_weights=_breakdown_weights(s),
    )
    batch_evaluation_service = BatchEvaluationService(
        orchestrator=dimension_evaluator,
        concurrency=s.batch_concurrency,
    )
    provider = MatchingProvider(
        dimension_evaluator=dimension_evaluator,
        match_analyzer=match_analyzer,
        batch_evaluation_service=batch_evaluation_service,
    )
    return MatchingBuild(
        provider=provider,
        dimension_evaluator=dimension_evaluator,
        match_analyzer=match_analyzer,
    )

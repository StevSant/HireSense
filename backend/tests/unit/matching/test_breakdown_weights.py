"""The configured heuristic weights must actually reach the composite score.

Regression guard: WEIGHT_SEMANTIC / WEIGHT_SKILL_MATCH / WEIGHT_EXPERIENCE /
WEIGHT_LANGUAGE were declared in config and shipped in .env.example but read by
nothing — MatchingOrchestrator called weighted_average() with no argument, so
the real blend was ScoreBreakdown's hardcoded default and setting them in .env
did nothing.
"""

import pytest

from hiresense.composition.matching import _breakdown_weights
from hiresense.matching.domain.models import ScoreBreakdown


class _Settings:
    def __init__(self, semantic: int, skill: int, experience: int, language: int) -> None:
        self.weight_semantic = semantic
        self.weight_skill_match = skill
        self.weight_experience = experience
        self.weight_language = language


def test_percentages_normalize_to_fractions_summing_to_one() -> None:
    weights = _breakdown_weights(_Settings(35, 30, 20, 15))

    assert weights == pytest.approx(
        {"semantic": 0.35, "skill": 0.30, "experience": 0.20, "language": 0.15}
    )
    assert sum(weights.values()) == pytest.approx(1.0)


def test_defaults_preserve_the_historical_blend() -> None:
    """The shipped defaults must reproduce ScoreBreakdown's old hardcoded ratios."""
    breakdown = ScoreBreakdown(
        semantic_score=1.0, skill_score=0.0, experience_score=0.0, language_score=0.0
    )

    assert breakdown.weighted_average(
        _breakdown_weights(_Settings(35, 30, 20, 15))
    ) == pytest.approx(breakdown.weighted_average())


def test_weights_change_the_composite() -> None:
    """Proves the wiring is live: different weights must move the score."""
    breakdown = ScoreBreakdown(
        semantic_score=1.0, skill_score=0.0, experience_score=0.0, language_score=0.0
    )

    semantic_heavy = breakdown.weighted_average(_breakdown_weights(_Settings(70, 10, 10, 10)))
    skill_heavy = breakdown.weighted_average(_breakdown_weights(_Settings(10, 70, 10, 10)))

    assert semantic_heavy == pytest.approx(0.7)
    assert skill_heavy == pytest.approx(0.1)


def test_non_hundred_totals_still_produce_a_weighted_average() -> None:
    """Weights are divided by their own total, not a literal 100."""
    weights = _breakdown_weights(_Settings(1, 1, 1, 1))

    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["semantic"] == pytest.approx(0.25)


def test_degenerate_zero_total_falls_back_to_defaults() -> None:
    """A zero-sum config must not divide by zero or score everything 0.0."""
    breakdown = ScoreBreakdown(
        semantic_score=1.0, skill_score=1.0, experience_score=1.0, language_score=1.0
    )
    weights = _breakdown_weights(_Settings(0, 0, 0, 0))

    assert weights == {}
    assert breakdown.weighted_average(weights) == pytest.approx(1.0)

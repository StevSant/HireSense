"""Tests for combine_fit_score weight injection (Work Unit B).

Written BEFORE implementation (TDD RED phase).
Verifies REQ-06: hardcoded module constants removed; weights become parameters.
"""

from __future__ import annotations

import pytest

from hiresense.ingestion.domain.job_scorer import combine_fit_score


class TestCombineFitScoreInjectedWeights:
    def test_combine_fit_score_uses_injected_weights(self) -> None:
        """When explicit weights are provided they override the defaults."""
        # skill_weight=1.0, semantic_weight=0.0 → result should be skill_score
        result = combine_fit_score(0.8, 0.2, skill_weight=1.0, semantic_weight=0.0)
        assert result is not None
        assert abs(result - 0.8) < 1e-9

    def test_combine_fit_score_defaults_reproduce_0_4_0_6(self) -> None:
        """Default parameters must produce the same result as the old hardcoded constants."""
        result = combine_fit_score(1.0, 0.0)
        assert result is not None
        assert abs(result - 0.4) < 1e-9

        result2 = combine_fit_score(0.0, 1.0)
        assert result2 is not None
        assert abs(result2 - 0.6) < 1e-9

    def test_weight_flip_reverses_order(self) -> None:
        """Swapping weights changes which job wins.

        Job A: high skill, low semantic → wins with skill_weight=0.9
        Job B: low skill, high semantic → wins with semantic_weight=0.9
        """
        skill_heavy_job_score = combine_fit_score(1.0, 0.1)  # default 0.4*1 + 0.6*0.1 = 0.46
        semantic_heavy_job_score = combine_fit_score(0.1, 1.0)  # default 0.4*0.1 + 0.6*1 = 0.64

        # With defaults: semantic-heavy job wins
        assert semantic_heavy_job_score > skill_heavy_job_score  # type: ignore[operator]

        # Flip to skill-dominant weights: skill-heavy job should now win
        skill_heavy_flipped = combine_fit_score(1.0, 0.1, skill_weight=0.9, semantic_weight=0.1)
        semantic_heavy_flipped = combine_fit_score(0.1, 1.0, skill_weight=0.9, semantic_weight=0.1)
        assert skill_heavy_flipped is not None
        assert semantic_heavy_flipped is not None
        assert skill_heavy_flipped > semantic_heavy_flipped

    def test_injected_zero_semantic_weight_returns_skill_score(self) -> None:
        """With semantic_weight=0 the result equals skill_score."""
        result = combine_fit_score(0.75, 0.99, skill_weight=1.0, semantic_weight=0.0)
        assert result is not None
        assert abs(result - 0.75) < 1e-9

    def test_injected_zero_skill_weight_returns_semantic_score(self) -> None:
        """With skill_weight=0 the result equals semantic_score."""
        result = combine_fit_score(0.99, 0.33, skill_weight=0.0, semantic_weight=1.0)
        assert result is not None
        assert abs(result - 0.33) < 1e-9

    def test_none_handling_unchanged_with_custom_weights(self) -> None:
        """Fallback behaviour for None inputs is unchanged when weights are supplied."""
        assert combine_fit_score(None, None, skill_weight=0.5, semantic_weight=0.5) is None
        assert combine_fit_score(0.7, None, skill_weight=0.5, semantic_weight=0.5) == pytest.approx(
            0.7
        )
        assert combine_fit_score(None, 0.5, skill_weight=0.5, semantic_weight=0.5) == pytest.approx(
            0.5
        )


def test_no_module_level_skill_weight_constant() -> None:
    """_SKILL_WEIGHT and _SEMANTIC_WEIGHT module constants must be removed."""
    import hiresense.ingestion.domain.job_scorer as scorer

    assert not hasattr(scorer, "_SKILL_WEIGHT"), (
        "_SKILL_WEIGHT must be removed — weights are now parameters"
    )
    assert not hasattr(scorer, "_SEMANTIC_WEIGHT"), (
        "_SEMANTIC_WEIGHT must be removed — weights are now parameters"
    )

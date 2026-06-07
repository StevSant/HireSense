from __future__ import annotations

from hiresense.preference.domain import OutcomeObservation, WeightNudgeCalculator


def _obs(dimension: str, score: float, polarity: int) -> OutcomeObservation:
    return OutcomeObservation(dimension=dimension, dimension_score=score, polarity=polarity)


def test_below_gate_returns_no_overrides():
    calc = WeightNudgeCalculator(min_outcomes=5, clamp=3, scale=5.0)
    # Only 3 outcome observations for the dimension -> gate (5) unmet.
    obs = [_obs("comp", 1.0, 1) for _ in range(3)]
    assert calc.compute_overrides(obs) == {}


def test_empty_returns_no_overrides():
    calc = WeightNudgeCalculator(min_outcomes=1, clamp=3, scale=5.0)
    assert calc.compute_overrides([]) == {}


def test_positive_correlation_nudges_up():
    calc = WeightNudgeCalculator(min_outcomes=5, clamp=3, scale=5.0)
    # Dimension scored high (1.0) on positive outcomes -> positive correlation.
    obs = [_obs("comp", 1.0, 1) for _ in range(5)]
    overrides = calc.compute_overrides(obs)
    assert overrides["comp"] > 0


def test_negative_correlation_nudges_down():
    calc = WeightNudgeCalculator(min_outcomes=5, clamp=3, scale=5.0)
    # Dimension scored high on NEGATIVE outcomes -> negative correlation.
    obs = [_obs("comp", 1.0, -1) for _ in range(5)]
    overrides = calc.compute_overrides(obs)
    assert overrides["comp"] < 0


def test_low_score_on_positive_outcome_nudges_down():
    calc = WeightNudgeCalculator(min_outcomes=5, clamp=3, scale=5.0)
    # Dimension scored LOW (0.0) on positive outcomes -> it failed to predict
    # the good outcomes -> nudge down.
    obs = [_obs("comp", 0.0, 1) for _ in range(5)]
    overrides = calc.compute_overrides(obs)
    assert overrides["comp"] < 0


def test_neutral_score_yields_no_delta():
    calc = WeightNudgeCalculator(min_outcomes=5, clamp=3, scale=5.0)
    # Score exactly at the neutral 0.5 -> zero correlation -> no entry.
    obs = [_obs("comp", 0.5, 1) for _ in range(5)]
    assert calc.compute_overrides(obs) == {}


def test_delta_is_clamped():
    # Huge scale would blow past the clamp; clamp must hold the bound.
    calc = WeightNudgeCalculator(min_outcomes=5, clamp=3, scale=1000.0)
    obs = [_obs("comp", 1.0, 1) for _ in range(5)]
    overrides = calc.compute_overrides(obs)
    assert overrides["comp"] == 3  # clamped to +clamp

    calc_neg = WeightNudgeCalculator(min_outcomes=5, clamp=3, scale=1000.0)
    obs_neg = [_obs("comp", 1.0, -1) for _ in range(5)]
    assert calc_neg.compute_overrides(obs_neg)["comp"] == -3


def test_gate_counts_per_dimension_observations():
    # 5 signals, each scoring two dimensions -> 5 observations per dimension,
    # which meets a gate of 5 (the gate is per outcome signal, not per row).
    calc = WeightNudgeCalculator(min_outcomes=5, clamp=3, scale=5.0)
    obs: list[OutcomeObservation] = []
    for _ in range(5):
        obs.append(_obs("comp", 1.0, 1))
        obs.append(_obs("culture", 0.0, 1))
    overrides = calc.compute_overrides(obs)
    assert overrides["comp"] > 0
    assert overrides["culture"] < 0


def test_independent_dimensions_get_independent_deltas():
    calc = WeightNudgeCalculator(min_outcomes=4, clamp=5, scale=10.0)
    obs: list[OutcomeObservation] = []
    for _ in range(4):
        obs.append(_obs("comp", 1.0, 1))      # strong positive
        obs.append(_obs("growth", 0.5, 1))    # neutral
    overrides = calc.compute_overrides(obs)
    assert overrides["comp"] == 5  # 0.5 * 10 = 5, clamped at 5
    assert "growth" not in overrides  # neutral -> zero -> omitted

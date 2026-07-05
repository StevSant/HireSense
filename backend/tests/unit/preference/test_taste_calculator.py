import math

from hiresense.preference.domain import SignalContribution, TasteVectorCalculator


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def test_decay_is_one_at_zero_age() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    assert calc.decay(0.0) == 1.0


def test_decay_decreases_with_age() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    assert calc.decay(90.0) < calc.decay(10.0) < 1.0


def test_empty_contributions_give_zero_delta() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    assert calc.compute_delta([], dim=3) == [0.0, 0.0, 0.0]


def test_positive_signal_points_delta_toward_embedding() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    delta = calc.compute_delta(
        [SignalContribution(embedding=[1.0, 0.0], polarity=1, weight=1.0, age_days=0.0)],
        dim=2,
    )
    assert delta[0] > 0.0 and delta[1] == 0.0


def test_negative_signal_points_delta_away() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    delta = calc.compute_delta(
        [SignalContribution(embedding=[1.0, 0.0], polarity=-1, weight=1.0, age_days=0.0)],
        dim=2,
    )
    assert delta[0] < 0.0


def test_older_signal_contributes_less_than_fresh() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    fresh = calc.compute_delta(
        [SignalContribution(embedding=[1.0, 0.0], polarity=1, weight=1.0, age_days=0.0)], dim=2
    )
    old = calc.compute_delta(
        [SignalContribution(embedding=[1.0, 0.0], polarity=1, weight=1.0, age_days=180.0)], dim=2
    )
    assert old[0] < fresh[0]


def test_blend_pulls_baseline_toward_delta_and_normalizes() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    taste = calc.blend([1.0, 0.0], [0.0, 1.0])
    assert math.isclose(_norm(taste), 1.0, rel_tol=1e-6)
    assert taste[1] > 0.0  # pulled toward the delta's axis


def test_blend_with_zero_delta_returns_normalized_baseline() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    taste = calc.blend([3.0, 4.0], [0.0, 0.0])
    assert math.isclose(taste[0], 0.6, rel_tol=1e-6)
    assert math.isclose(taste[1], 0.8, rel_tol=1e-6)


def test_decay_with_nonpositive_tau_returns_one() -> None:
    zero_tau = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=0.0)
    assert zero_tau.decay(50.0) == 1.0
    negative_tau = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=-1.0)
    assert negative_tau.decay(50.0) == 1.0


def test_compute_delta_skips_dimension_mismatch() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    valid = SignalContribution(embedding=[1.0, 0.0], polarity=1, weight=1.0, age_days=0.0)
    mismatched = SignalContribution(embedding=[1.0, 1.0, 1.0], polarity=1, weight=1.0, age_days=0.0)
    delta_mixed = calc.compute_delta([valid, mismatched], dim=2)
    delta_valid_only = calc.compute_delta([valid], dim=2)
    assert delta_mixed == delta_valid_only


def test_blend_with_zero_baseline_and_zero_delta_returns_zeros() -> None:
    calc = TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0)
    assert calc.blend([0.0, 0.0], [0.0, 0.0]) == [0.0, 0.0]

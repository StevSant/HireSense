"""Tests for the single-signal renormalization contract of combine_fit_score (#160).

When only one of skill/semantic is present the blend must renormalize over the
present weight(s) so the result stays on the same [0, 1] scale as a two-signal
blend, rather than being an arbitrary down-weight that biases the global sort.
"""

from __future__ import annotations

import pytest

from hiresense.ingestion.domain.job_scorer import combine_fit_score


class TestSingleSignalRenormalization:
    def test_skill_only_renormalizes_to_raw_skill_regardless_of_weight(self) -> None:
        # 0.4*0.8 / 0.4 == 0.8 — the lone signal's weight scales up to 1.0.
        assert combine_fit_score(0.8, None) == pytest.approx(0.8)
        assert combine_fit_score(0.8, None, skill_weight=0.1, semantic_weight=0.9) == pytest.approx(
            0.8
        )

    def test_semantic_only_renormalizes_to_raw_semantic(self) -> None:
        assert combine_fit_score(None, 0.5) == pytest.approx(0.5)
        assert combine_fit_score(None, 0.5, skill_weight=0.9, semantic_weight=0.1) == pytest.approx(
            0.5
        )

    def test_mixed_present_and_absent_stay_on_the_same_scale(self) -> None:
        # A skill-only job and a both-signal job with the SAME skill component
        # must be comparable: the single-signal job is renormalized to its raw
        # skill (0.8), not down-weighted to 0.4*0.8 = 0.32.
        skill_only = combine_fit_score(0.8, None)
        both = combine_fit_score(0.8, 0.8)
        assert skill_only == pytest.approx(0.8)
        assert both == pytest.approx(0.8)
        assert skill_only == pytest.approx(both)

    def test_two_signal_blend_is_plain_weighted_average_with_default_weights(self) -> None:
        # Defaults sum to 1.0 so renormalization is a no-op for the two-signal
        # case — existing behaviour is preserved.
        assert combine_fit_score(1.0, 0.0) == pytest.approx(0.4)
        assert combine_fit_score(0.0, 1.0) == pytest.approx(0.6)

    def test_returns_none_when_present_weights_sum_to_zero(self) -> None:
        # A signal whose weight is zero carries no basis to blend on.
        assert combine_fit_score(0.8, None, skill_weight=0.0, semantic_weight=0.6) is None

    def test_returns_none_when_no_signal_present(self) -> None:
        assert combine_fit_score(None, None) is None

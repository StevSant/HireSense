from __future__ import annotations


from hiresense.ingestion.domain.job_scorer import combine_fit_score


def test_both_none_returns_none() -> None:
    assert combine_fit_score(None, None) is None


def test_only_skill_returns_skill() -> None:
    assert combine_fit_score(0.7, None) == 0.7


def test_only_semantic_returns_semantic() -> None:
    assert combine_fit_score(None, 0.5) == 0.5


def test_weighted_combination() -> None:
    result = combine_fit_score(1.0, 0.0)
    assert result is not None
    assert abs(result - 0.4) < 1e-9


def test_semantic_weighs_more_than_skill() -> None:
    semantic_only = combine_fit_score(0.0, 1.0)
    skill_only = combine_fit_score(1.0, 0.0)
    assert semantic_only is not None and skill_only is not None
    assert semantic_only > skill_only


def test_zero_scores_combine_to_zero() -> None:
    assert combine_fit_score(0.0, 0.0) == 0.0


def test_full_scores_combine_to_one() -> None:
    result = combine_fit_score(1.0, 1.0)
    assert result is not None
    assert abs(result - 1.0) < 1e-9

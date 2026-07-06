from hiresense.matching.domain.scorers.base import DimensionResult


def test_dimension_result_creation() -> None:
    result = DimensionResult(
        dimension="seniority_fit", score=0.8, rationale="Good seniority match", weight=10
    )
    assert result.dimension == "seniority_fit"
    assert result.score == 0.8
    assert result.rationale == "Good seniority match"
    assert result.weight == 10


def test_dimension_result_score_clamped() -> None:
    result = DimensionResult(dimension="test", score=1.5, rationale="x", weight=10)
    assert result.score == 1.0
    result2 = DimensionResult(dimension="test", score=-0.5, rationale="x", weight=10)
    assert result2.score == 0.0


def test_dimension_result_default_score() -> None:
    result = DimensionResult.default("seniority_fit", weight=10, rationale="LLM not configured")
    assert result.score == 0.5
    assert result.dimension == "seniority_fit"
    assert result.rationale == "LLM not configured"

import math

from hiresense.matching.domain.semantic_scorer import SemanticScorer


def test_identical_embeddings_score_one() -> None:
    scorer = SemanticScorer()
    embedding = [1.0, 0.0, 0.0]
    score = scorer.cosine_similarity(embedding, embedding)
    assert math.isclose(score, 1.0, abs_tol=1e-6)


def test_orthogonal_embeddings_score_zero() -> None:
    scorer = SemanticScorer()
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    score = scorer.cosine_similarity(a, b)
    assert math.isclose(score, 0.0, abs_tol=1e-6)


def test_opposite_embeddings_score_negative() -> None:
    scorer = SemanticScorer()
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    score = scorer.cosine_similarity(a, b)
    assert score < 0


def test_similar_embeddings_high_score() -> None:
    scorer = SemanticScorer()
    a = [1.0, 0.8, 0.6]
    b = [0.9, 0.85, 0.55]
    score = scorer.cosine_similarity(a, b)
    assert score > 0.95


def test_zero_vector_returns_zero() -> None:
    scorer = SemanticScorer()
    a = [0.0, 0.0, 0.0]
    b = [1.0, 2.0, 3.0]
    score = scorer.cosine_similarity(a, b)
    assert score == 0.0


def test_score_normalized_to_range() -> None:
    """score() should clamp cosine similarity to [0, 1] for use as a match score."""
    scorer = SemanticScorer()
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    score = scorer.score(a, b)
    assert 0.0 <= score <= 1.0

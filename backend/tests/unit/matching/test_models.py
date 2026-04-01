from hiresense.matching.domain.models import MatchResult, ScoreBreakdown


def test_score_breakdown_creation() -> None:
    breakdown = ScoreBreakdown(
        semantic_score=0.85,
        skill_score=0.70,
        experience_score=0.60,
        language_score=1.0,
    )
    assert breakdown.semantic_score == 0.85
    assert breakdown.skill_score == 0.70


def test_score_breakdown_weighted_average() -> None:
    breakdown = ScoreBreakdown(
        semantic_score=0.80,
        skill_score=0.60,
        experience_score=0.70,
        language_score=1.0,
    )
    avg = breakdown.weighted_average()
    assert 0.0 <= avg <= 1.0
    assert isinstance(avg, float)


def test_match_result_creation() -> None:
    breakdown = ScoreBreakdown(
        semantic_score=0.85,
        skill_score=0.70,
        experience_score=0.60,
        language_score=1.0,
    )
    result = MatchResult(
        id="match-1",
        job_id="job-1",
        cv_id="cv-1",
        overall_score=0.78,
        breakdown=breakdown,
        matched_skills=["python", "fastapi"],
        missing_skills=["kubernetes", "terraform"],
        pros=["Strong Python experience"],
        cons=["No cloud infrastructure experience"],
        recommendations=["Learn Kubernetes basics"],
    )
    assert result.overall_score == 0.78
    assert "python" in result.matched_skills
    assert "kubernetes" in result.missing_skills
    assert len(result.pros) == 1


def test_match_result_optional_fields() -> None:
    breakdown = ScoreBreakdown(
        semantic_score=0.5,
        skill_score=0.5,
        experience_score=0.5,
        language_score=0.5,
    )
    result = MatchResult(
        id="match-2",
        job_id="job-2",
        cv_id="cv-2",
        overall_score=0.5,
        breakdown=breakdown,
    )
    assert result.matched_skills == []
    assert result.missing_skills == []
    assert result.pros == []
    assert result.cons == []
    assert result.recommendations == []

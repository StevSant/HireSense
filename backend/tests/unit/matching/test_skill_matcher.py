from hiresense.matching.domain.skill_matcher import SkillMatcher, SkillMatchResult


def test_perfect_match() -> None:
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["python", "fastapi", "postgresql"],
        required_skills=["python", "fastapi", "postgresql"],
    )
    assert result.score == 1.0
    assert result.missing == []
    assert sorted(result.matched) == ["fastapi", "postgresql", "python"]


def test_partial_match() -> None:
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["python", "fastapi"],
        required_skills=["python", "fastapi", "kubernetes", "terraform"],
    )
    assert 0.0 < result.score < 1.0
    assert sorted(result.matched) == ["fastapi", "python"]
    assert sorted(result.missing) == ["kubernetes", "terraform"]


def test_no_match() -> None:
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["java", "spring"],
        required_skills=["python", "fastapi"],
    )
    assert result.score == 0.0
    assert result.matched == []
    assert sorted(result.missing) == ["fastapi", "python"]


def test_case_insensitive() -> None:
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["Python", "FastAPI"],
        required_skills=["python", "fastapi"],
    )
    assert result.score == 1.0
    assert len(result.matched) == 2


def test_empty_required_skills() -> None:
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["python"],
        required_skills=[],
    )
    assert result.score == 1.0
    assert result.missing == []


def test_extra_candidate_skills_ignored() -> None:
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["python", "fastapi", "django", "flask", "docker"],
        required_skills=["python", "fastapi"],
    )
    assert result.score == 1.0
    assert sorted(result.matched) == ["fastapi", "python"]
    assert result.missing == []

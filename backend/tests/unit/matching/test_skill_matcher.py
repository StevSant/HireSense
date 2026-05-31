from hiresense.matching.domain.skill_matcher import SkillMatcher


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


def test_matches_skill_with_parenthetical_qualifier() -> None:
    # Candidate lists "Python (primary)"; the job asks for "python".
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["Python (primary)", "Golang"],
        required_skills=["python", "go"],
    )
    assert result.score == 1.0
    assert sorted(result.matched) == ["go", "python"]
    assert result.missing == []


def test_matches_via_alias() -> None:
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["Postgres", "JS"],
        required_skills=["postgresql", "javascript"],
    )
    assert result.score == 1.0
    assert result.missing == []


def test_matches_skill_evidenced_in_experience_text() -> None:
    # "distributed systems" is not in the explicit skills list but is clearly
    # demonstrated in the candidate's experience text.
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["python", "fastapi"],
        required_skills=["python", "distributed systems"],
        evidence_text="Experience building distributed systems with Kafka and Redis.",
    )
    assert result.score == 1.0
    assert sorted(result.matched) == ["distributed systems", "python"]
    assert result.missing == []


def test_evidence_does_not_create_substring_false_positive() -> None:
    # Required "java" must NOT be satisfied by the word "javascript" in evidence.
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["python"],
        required_skills=["java"],
        evidence_text="Senior javascript developer with python.",
    )
    assert result.missing == ["java"]
    assert result.matched == []


def test_missing_skill_absent_from_both_list_and_evidence() -> None:
    matcher = SkillMatcher()
    result = matcher.match(
        candidate_skills=["python"],
        required_skills=["python", "rust"],
        evidence_text="Backend engineer focused on Python services.",
    )
    assert sorted(result.matched) == ["python"]
    assert result.missing == ["rust"]

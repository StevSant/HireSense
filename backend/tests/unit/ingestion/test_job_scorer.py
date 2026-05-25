from __future__ import annotations

from hiresense.ingestion.domain.job_scorer import score_job_against_skills, score_jobs
from hiresense.ingestion.domain.models import NormalizedJob


def _job(skills: list[str]) -> NormalizedJob:
    return NormalizedJob(
        id="1",
        title="x",
        company="x",
        description="x",
        skills=skills,
        source="x",
        source_type="api",
        url="x",
    )


def test_score_none_when_job_has_no_required_skills() -> None:
    assert score_job_against_skills(_job([]), {"python"}) is None


def test_score_full_match() -> None:
    result = score_job_against_skills(_job(["Python", "FastAPI"]), {"python", "fastapi"})
    assert result == 1.0


def test_score_partial_match() -> None:
    result = score_job_against_skills(_job(["Python", "FastAPI", "AWS"]), {"python"})
    assert result is not None
    assert abs(result - 1 / 3) < 1e-9


def test_score_no_match() -> None:
    result = score_job_against_skills(_job(["Python"]), {"go", "rust"})
    assert result == 0.0


def test_score_case_insensitive() -> None:
    result = score_job_against_skills(_job(["PYTHON"]), {"python"})
    assert result == 1.0


def test_score_jobs_attaches_scores() -> None:
    jobs = [_job(["Python"]), _job(["Go"])]
    scored = score_jobs(jobs, ["python"])
    assert scored[0].match_score == 1.0
    assert scored[1].match_score == 0.0


def test_score_jobs_empty_candidate_skills_returns_unchanged() -> None:
    jobs = [_job(["Python"])]
    result = score_jobs(jobs, [])
    assert result is jobs  # no copy, no work
    assert result[0].match_score is None


def test_score_jobs_does_not_mutate_input() -> None:
    jobs = [_job(["Python"])]
    score_jobs(jobs, ["python"])
    assert jobs[0].match_score is None

from __future__ import annotations

from hiresense.ingestion.domain.models import NormalizedJob

_SKILL_WEIGHT = 0.4
_SEMANTIC_WEIGHT = 0.6


def combine_fit_score(
    skill_score: float | None,
    semantic_score: float | None,
) -> float | None:
    """Combine skill-overlap and semantic-similarity into a single fit score.

    Both signals are independently informative, so we weight semantic higher
    (it captures meaning beyond exact skill-name matches) but still let skill
    overlap pull the score up when the job actually lists matching skills.
    Falls back gracefully when either input is missing.
    """
    if skill_score is None and semantic_score is None:
        return None
    if skill_score is None:
        return semantic_score
    if semantic_score is None:
        return skill_score
    return _SKILL_WEIGHT * skill_score + _SEMANTIC_WEIGHT * semantic_score


def score_job_against_skills(
    job: NormalizedJob,
    candidate_skills: set[str],
) -> float | None:
    """Lightweight skill-overlap score in [0.0, 1.0].

    Returns None when the job has no listed required skills, signalling
    "can't score" rather than "perfect match" — the frontend renders this
    as a neutral '—' rather than a misleading 100%.
    """
    required = [s.lower() for s in job.skills if s]
    if not required:
        return None
    matched = sum(1 for s in required if s in candidate_skills)
    return matched / len(required)


def score_jobs(
    jobs: list[NormalizedJob],
    candidate_skills: list[str],
) -> list[NormalizedJob]:
    """Return new NormalizedJob instances with match_score populated."""
    skill_set = {s.lower() for s in candidate_skills if s}
    if not skill_set:
        return jobs
    return [
        job.model_copy(update={"match_score": score_job_against_skills(job, skill_set)})
        for job in jobs
    ]

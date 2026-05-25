from __future__ import annotations

from hiresense.ingestion.domain.models import NormalizedJob


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

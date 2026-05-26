from __future__ import annotations

import re

from hiresense.ingestion.domain.models import NormalizedJob

_SKILL_WEIGHT = 0.4
_SEMANTIC_WEIGHT = 0.6

# Each candidate-skill mention in a job's title/description adds this much to
# the fallback text score, capped at 1.0. 4 mentions = "strong fit".
_TEXT_MENTION_WEIGHT = 0.25
_TEXT_MENTION_CAP = 1.0

# Cap on the denominator in the skill-overlap formula. Sources like getonboard
# attach 15–30+ tag IDs per job; using the raw len(required) as the divisor
# penalises them vs. tight skill lists (1 hit / 20 tags = 0.05, 1 hit / 5 = 0.20).
# 10 is roughly the "fair denominator" — close to the median tag count across
# well-curated sources — so overlap dominates above that.
_SKILL_DILUTION_CAP = 10


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


def _text_mention_score(text: str, candidate_skills: set[str]) -> float | None:
    """Fallback for jobs with no structured `skills` list.

    Counts whole-word candidate-skill mentions in title + description. Each
    mention is worth `_TEXT_MENTION_WEIGHT` (capped at 1.0). Returns None
    when neither the text nor the candidate skill list is usable.
    """
    if not text or not candidate_skills:
        return None
    # Escape skills and join into a single alternation so we walk the text
    # once. Word boundaries prevent "go" matching "django" or "tango".
    escaped = sorted({re.escape(s) for s in candidate_skills if s}, key=len, reverse=True)
    if not escaped:
        return None
    pattern = re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)
    distinct = {m.group(0).lower() for m in pattern.finditer(text)}
    if not distinct:
        return None
    return min(len(distinct) * _TEXT_MENTION_WEIGHT, _TEXT_MENTION_CAP)


def score_job_against_skills(
    job: NormalizedJob,
    candidate_skills: set[str],
) -> float | None:
    """Lightweight skill-overlap score in [0.0, 1.0].

    Prefers the job's structured `skills` field when populated. Falls back
    to a whole-word scan of `title + description` for sources like HN and
    portal scrapers that ship without parsed skills. Returns None when
    neither signal yields any match — the frontend renders this as a
    neutral '—' rather than a misleading 0%.
    """
    required = [s.lower() for s in job.skills if s]
    if required:
        matched = sum(1 for s in required if s in candidate_skills)
        denom = min(len(required), _SKILL_DILUTION_CAP)
        return min(matched / denom, 1.0)
    return _text_mention_score(f"{job.title}\n{job.description}", candidate_skills)


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

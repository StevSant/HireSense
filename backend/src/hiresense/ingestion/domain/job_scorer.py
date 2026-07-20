from __future__ import annotations

import re

from hiresense.ingestion.domain.models import NormalizedJob

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

# Default pre-ranking blend weights. These reproduce the previous hardcoded
# 0.4/0.6 behaviour and match Settings.prerank_weight_skill/semantic defaults.
# Call sites that read from Settings should pass explicit values instead.
_DEFAULT_SKILL_WEIGHT = 0.4
_DEFAULT_SEMANTIC_WEIGHT = 0.6


def combine_fit_score(
    skill_score: float | None,
    semantic_score: float | None,
    *,
    skill_weight: float = _DEFAULT_SKILL_WEIGHT,
    semantic_weight: float = _DEFAULT_SEMANTIC_WEIGHT,
) -> float | None:
    """Combine skill-overlap and semantic-similarity into a single fit score.

    Both signals are independently informative. The caller controls the blend
    via ``skill_weight`` / ``semantic_weight``; the defaults reproduce the
    previous hardcoded 0.4/0.6 behaviour so existing call sites are unaffected.

    Single-signal contract (#160): when only one signal is present the blend is
    renormalized over the *present* weights — the lone signal's weight is scaled
    up to 1.0 — so the result stays on the same [0, 1] scale as a two-signal
    blend and jobs rank consistently no matter how many signals they carry
    (the pre-ranker only sets semantic on ANN-indexed jobs, so the corpus is a
    mix of one- and two-signal jobs). Concretely a skill-only job scores its raw
    skill value (``skill_weight*skill / skill_weight``) instead of an arbitrary
    down-weight, and likewise for a semantic-only job. With both signals present
    and default weights that sum to 1.0 this is the plain weighted average, so
    existing behaviour is unchanged.

    Returns None when neither signal is present, or when the present weights sum
    to zero (no basis on which to blend).
    """
    weighted: list[tuple[float, float]] = []
    if skill_score is not None:
        weighted.append((skill_weight, skill_score))
    if semantic_score is not None:
        weighted.append((semantic_weight, semantic_score))
    if not weighted:
        return None
    if len(weighted) == 1:
        # Single-signal case: renormalizing over one present weight scales it to
        # 1.0, i.e. the result IS the raw score. Return it directly so the value
        # is exact (a `w*s/w` division would introduce float drift), and drop it
        # to None when that lone signal carries zero weight (no basis to rank).
        weight, score = weighted[0]
        return score if weight > 0 else None
    total_weight = sum(weight for weight, _ in weighted)
    if total_weight <= 0:
        return None
    return sum(weight * score for weight, score in weighted) / total_weight


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

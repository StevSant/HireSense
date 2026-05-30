from __future__ import annotations

from hiresense.ingestion.domain.seniority import SeniorityLevel, detect_seniority


def infer_candidate_level(summary: str) -> SeniorityLevel:
    """Best-effort candidate seniority inferred from CV text.

    Reuses the job-side seniority heuristics (intern/junior/senior keywords +
    stated years of experience) against the candidate's own CV. Crucially it
    NEVER assumes mid-level: when the CV gives no clear signal it returns
    UNKNOWN, and the LLM prompt is then told to infer conservatively rather
    than against a mid-level baseline (the bug that let senior roles score
    high for junior candidates).

    The CV text is passed as the *description* argument so only the
    body-safe keyword rules (intern/junior/senior) apply — this avoids a
    stray "lead" (e.g. "Content Management Lead") inflating the level.
    """
    return detect_seniority("", summary)

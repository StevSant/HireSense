from __future__ import annotations

from hiresense.kernel.prompts import BATCH_SCORING_CONSEQUENCES, render_gating_rules


def render_quick_scoring_system_prompt() -> str:
    """Static half of the batched list-scoring system prompt.

    Callers append the CANDIDATE block to this; see
    QuickScoringService._build_system_prompt, which depends on this prefix being
    byte-stable so Anthropic prompt caching can reuse it across chunks and runs.
    Because this is assembled from constants only, it renders identically on
    every call — the caching contract holds.
    """
    return (
        "You are a precise technical recruiter scoring how well a CANDIDATE fits "
        "each JOB. Return ONLY a JSON array — one object per job, in input order:\n"
        '[{"ref": <job number>, "score": <0.0-1.0>, '
        '"verdict": "strong|moderate|weak", '
        '"reasons": ["short evidence", ...], '
        '"dealbreakers": ["hard mismatch", ...]}]\n\n'
        f"{render_gating_rules(BATCH_SCORING_CONSEQUENCES)}"
    )

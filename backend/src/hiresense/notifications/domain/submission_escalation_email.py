from __future__ import annotations

from typing import Any

# A single escalation email should be scannable, not exhaustive. Beyond this
# the message just says how many more are waiting.
MAX_LISTED = 10


def render_submission_escalation_email(attempts: list[Any]) -> tuple[str, str]:
    """Render an auto-apply escalation alert into (subject, plain-text body).

    Escalations are the manual fallback path: the agent stopped because it
    could not ground an answer, and the application will not go out until a
    human supplies one. The body names the specific question so the candidate
    can decide whether it is worth answering without opening the app.
    """
    count = len(attempts)
    noun = "application" if count == 1 else "applications"
    verb = "needs" if count == 1 else "need"
    subject = f"HireSense: {count} {noun} {verb} your answer before applying"

    lines = [
        f"Auto-apply paused {count} {noun} because it could not answer a question "
        "from your profile, your verified claims, or the job posting.",
        "",
    ]
    for attempt in attempts[:MAX_LISTED]:
        job = getattr(attempt, "job_id", "") or "unknown job"
        reason = getattr(attempt, "escalation_reason", None) or "needs review"
        lines.append(f"- {job}: {reason}")
    remaining = count - MAX_LISTED
    if remaining > 0:
        lines.append(f"- ...and {remaining} more")

    lines += [
        "",
        "Open HireSense to answer these. Answers you give are saved to your "
        "profile, so the same question will not be asked again.",
    ]
    return subject, "\n".join(lines)

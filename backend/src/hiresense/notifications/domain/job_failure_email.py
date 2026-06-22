from __future__ import annotations


def render_job_failure_email(job_name: str, detail: str | None) -> tuple[str, str]:
    """Render a scheduled-job failure alert into (subject, plain-text body)."""
    subject = f"HireSense: scheduled job '{job_name}' failed"
    body = (
        f"The scheduled job '{job_name}' failed during its last run.\n\n"
        f"Error: {detail or '(no detail)'}\n\n"
        "Check the scheduler admin page for run history."
    )
    return subject, body

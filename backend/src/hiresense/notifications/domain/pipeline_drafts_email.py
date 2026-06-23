from __future__ import annotations


def render_pipeline_drafts_email(count: int) -> tuple[str, str]:
    """Render an autopilot-drafts alert into (subject, plain-text body)."""
    noun = "draft" if count == 1 else "drafts"
    subject = f"HireSense: {count} application {noun} ready to review"
    body = (
        f"Autopilot prepared {count} application {noun} (CV + cover letter) for your "
        "top new matches.\n\nOpen HireSense to review, edit, and apply."
    )
    return subject, body

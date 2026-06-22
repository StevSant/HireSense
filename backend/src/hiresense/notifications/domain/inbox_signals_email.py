from __future__ import annotations


def render_inbox_signals_email(count: int) -> tuple[str, str]:
    """Render an inbox-signals alert into (subject, plain-text body)."""
    noun = "signal" if count == 1 else "signals"
    subject = f"HireSense: {count} new application {noun} detected"
    body = (
        f"{count} new email {noun} were detected from your inbox.\n\n"
        "Open HireSense to review and confirm the proposed tracking updates."
    )
    return subject, body

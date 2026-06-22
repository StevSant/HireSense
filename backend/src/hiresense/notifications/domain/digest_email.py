from __future__ import annotations

from typing import Any


def render_digest_email(digest: Any) -> tuple[str, str]:
    """Render a new-matches digest into (subject, plain-text body)."""
    count = digest.job_count
    subject = f"HireSense: {count} new job match{'es' if count != 1 else ''}"
    lines = [f"{count} new match{'es' if count != 1 else ''} found:", ""]
    for entry in digest.entries:
        score_pct = round(entry.score * 100)
        line = f"- {entry.title} · {entry.company} ({score_pct}%)"
        if entry.url:
            line += f"\n  {entry.url}"
        lines.append(line)
    lines.append("")
    lines.append("Open HireSense to review and apply.")
    return subject, "\n".join(lines)

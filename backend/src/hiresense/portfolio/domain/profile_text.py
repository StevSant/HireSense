from __future__ import annotations

from hiresense.portfolio.domain.portfolio_project import PortfolioProject

_UNPOSITIONED = 1_000_000


def portfolio_profile_text(
    projects: list[PortfolioProject], *, language: str, char_cap: int
) -> str:
    """Compact 'Portfolio projects' block for profile enrichment.

    Pinned projects first, then by position; one line per project
    (title [tech]: first description line); hard-capped at `char_cap`.
    """
    if not projects:
        return ""
    ordered = sorted(
        projects,
        key=lambda p: (not p.pinned, p.position if p.position is not None else _UNPOSITIONED),
    )
    lines = ["Portfolio projects:"]
    for project in ordered:
        text = project.text_for(language)
        if text is None:
            continue
        line = f"- {text.title}"
        if project.tech:
            line += f" [{', '.join(project.tech)}]"
        first_desc_line = (text.description or "").strip().splitlines()
        if first_desc_line and first_desc_line[0]:
            line += f": {first_desc_line[0]}"
        lines.append(line)
    return "\n".join(lines)[:char_cap]

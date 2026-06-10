from __future__ import annotations

from hiresense.portfolio.domain.portfolio_project import PortfolioProject

_UNPOSITIONED = 1_000_000
_HEADER = "Portfolio projects:"


def portfolio_profile_text(
    projects: list[PortfolioProject], *, language: str, char_cap: int
) -> str:
    """Compact 'Portfolio projects' block for profile enrichment.

    Pinned projects first, then by position; one line per project
    (title [tech]: first description line); hard-capped at `char_cap`.
    """
    # A cap that can't fit the header plus any content would yield a
    # truncated fragment in the LLM-facing summary — return nothing instead.
    if not projects or char_cap <= len(_HEADER):
        return ""
    ordered = sorted(
        projects,
        key=lambda p: (not p.pinned, p.position if p.position is not None else _UNPOSITIONED),
    )
    lines = [_HEADER]
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

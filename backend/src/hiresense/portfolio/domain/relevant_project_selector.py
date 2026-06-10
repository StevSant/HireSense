from __future__ import annotations

import re

from hiresense.portfolio.domain.portfolio_project import PortfolioProject

_TOKEN_RE = re.compile(r"[a-z0-9_+#.]+")
_UNPOSITIONED = 1_000_000


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


class RelevantProjectSelector:
    """Ranks portfolio projects against a job, deterministically (no LLM).

    Score = overlap between the job's terms (skills + description tokens) and
    the project's terms (tech + title tokens). Zero-score projects are never
    cited; ties break pinned-first, then by position.
    """

    def select(
        self,
        *,
        job_skills: list[str],
        job_text: str,
        projects: list[PortfolioProject],
        top_n: int,
    ) -> list[PortfolioProject]:
        job_terms = {skill.lower() for skill in job_skills} | _tokens(job_text)
        scored: list[tuple[int, PortfolioProject]] = []
        for project in projects:
            title = project.text_for("en")
            project_terms = {tech.lower() for tech in project.tech}
            if title is not None:
                project_terms |= _tokens(title.title)
            score = len(project_terms & job_terms)
            if score > 0:
                scored.append((score, project))
        scored.sort(
            key=lambda pair: (
                -pair[0],
                not pair[1].pinned,
                pair[1].position if pair[1].position is not None else _UNPOSITIONED,
            )
        )
        return [project for _, project in scored[:top_n]]

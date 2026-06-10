from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from hiresense.portfolio.domain.relevant_project_selector import RelevantProjectSelector

if TYPE_CHECKING:
    from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort


class PortfolioCitationService:
    """Builds the optional 'relevant portfolio projects' prompt block for
    generated artifacts (cover letters, outreach), including the
    per-application tracked link. Returns None when there is nothing
    relevant to cite — consumers then behave exactly as before."""

    def __init__(
        self,
        repository: PortfolioProjectsRepositoryPort,
        selector: RelevantProjectSelector,
        *,
        language: str,
        top_n: int,
        public_url: str,
        ref_prefix: str,
    ) -> None:
        self._repository = repository
        self._selector = selector
        self._language = language
        self._top_n = top_n
        self._public_url = public_url.rstrip("/")
        self._ref_prefix = ref_prefix

    async def citation_for(
        self,
        *,
        job_skills: list[str],
        job_text: str,
        application_id: str,
        language: str | None = None,
    ) -> str | None:
        projects = await asyncio.to_thread(self._repository.list_all)
        if not projects:
            return None
        picked = self._selector.select(
            job_skills=job_skills, job_text=job_text, projects=projects, top_n=self._top_n
        )
        if not picked:
            return None
        lang = language or self._language
        lines = [
            "Relevant portfolio projects (mention 1-2 naturally where they strengthen the case):"
        ]
        for project in picked:
            text = project.text_for(lang)
            if text is None:
                continue
            line = f"- {text.title}"
            if project.tech:
                line += f" [{', '.join(project.tech)}]"
            first_desc = (text.description or "").strip().splitlines()
            if first_desc and first_desc[0]:
                line += f": {first_desc[0]}"
            links = [link for link in (project.url, project.demo_url) if link]
            if links:
                line += f" ({' | '.join(links)})"
            lines.append(line)
        if len(lines) == 1:
            return None
        if self._public_url:
            lines.append(
                "Include this exact portfolio link once, near the close: "
                f"{self._public_url}/?ref={self._ref_prefix}-{application_id}"
            )
        return "\n".join(lines)

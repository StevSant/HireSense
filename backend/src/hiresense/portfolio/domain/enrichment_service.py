from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from hiresense.portfolio.domain.profile_text import portfolio_profile_text

if TYPE_CHECKING:
    from hiresense.portfolio.ports.projects_repository import PortfolioProjectsRepositoryPort


class PortfolioEnrichmentService:
    """Produces the (extra skills, extra summary text) pair consumed by the
    ingestion/matching profile assembly. Empty snapshot ⇒ ([], "")."""

    def __init__(
        self,
        repository: "PortfolioProjectsRepositoryPort",
        *,
        language: str,
        char_cap: int,
    ) -> None:
        self._repository = repository
        self._language = language
        self._char_cap = char_cap

    async def enrichment(self) -> tuple[list[str], str]:
        projects = await asyncio.to_thread(self._repository.list_for_matching)
        if not projects:
            return [], ""
        skills = sorted({tech for project in projects for tech in project.tech})
        text = portfolio_profile_text(projects, language=self._language, char_cap=self._char_cap)
        return skills, text

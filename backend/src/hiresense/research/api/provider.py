from __future__ import annotations

from hiresense.research.domain import CompanyResearchService


class ResearchProvider:
    def __init__(self, research_service: CompanyResearchService) -> None:
        self._research_service = research_service

    def get_research_service(self) -> CompanyResearchService:
        return self._research_service

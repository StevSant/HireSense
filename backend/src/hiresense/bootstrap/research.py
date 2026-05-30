from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.research.api.provider import ResearchProvider
from hiresense.research.domain import CompanyResearchService
from hiresense.research.infrastructure import CompanyResearchRepository


def build_research(infra: SharedInfra, tracked: Callable[[str], Any]) -> ResearchProvider:
    research_repo = CompanyResearchRepository(session_factory=infra.sync_session_factory)
    research_service = CompanyResearchService(
        llm=tracked("company_research"),
        repository=research_repo,
    )
    return ResearchProvider(research_service=research_service)

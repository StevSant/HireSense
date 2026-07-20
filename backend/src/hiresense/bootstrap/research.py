from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.research.api.provider import ResearchProvider
from hiresense.research.domain import CompanyResearchService
from hiresense.research.infrastructure import (
    CompanyProfileFirmographicsAdapter,
    CompanyResearchRepository,
    CompositeFirmographicsAdapter,
    ExternalFirmographicsAdapter,
)


def build_research(infra: SharedInfra, tracked: Callable[[str], Any]) -> ResearchProvider:
    research_repo = CompanyResearchRepository(session_factory=infra.sync_session_factory)
    s = infra.settings
    external = ExternalFirmographicsAdapter(
        provider_url=s.firmographics_provider_url,
        api_key=s.firmographics_api_key,
    )
    # Prefer source-captured profiles (description/website/HQ from ingestion),
    # then the external provider (industry/size). The source profile is what
    # grounds the prompt for companies the LLM has no recall of (#178).
    providers: list[Any] = []
    if infra.company_profile_store is not None:
        providers.append(CompanyProfileFirmographicsAdapter(infra.company_profile_store))
    providers.append(external)
    firmographics = CompositeFirmographicsAdapter(providers)
    research_service = CompanyResearchService(
        llm=tracked("company_research"),
        repository=research_repo,
        firmographics=firmographics,
    )
    return ResearchProvider(research_service=research_service)

from __future__ import annotations

from fastapi import Request

from hiresense.portfolio.domain import (
    PortfolioEngagementService,
    PortfolioEnrichmentService,
    PortfolioSyncService,
)
from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort


def _provider(request: Request):
    return getattr(request.app.state, "portfolio", None)


def get_sync_service(request: Request) -> PortfolioSyncService | None:
    provider = _provider(request)
    return provider.get_sync_service() if provider else None


def get_projects_repository(request: Request) -> PortfolioProjectsRepositoryPort | None:
    provider = _provider(request)
    return provider.get_repository() if provider else None


def get_portfolio_enrichment(request: Request) -> PortfolioEnrichmentService | None:
    provider = _provider(request)
    return provider.get_enrichment_service() if provider else None


def get_engagement_service(request: Request) -> PortfolioEngagementService | None:
    provider = _provider(request)
    if provider is None:
        return None
    return provider.get_engagement_service()

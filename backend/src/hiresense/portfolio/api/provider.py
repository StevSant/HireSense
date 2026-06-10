from __future__ import annotations

from hiresense.portfolio.domain import (
    PortfolioCitationService,
    PortfolioEnrichmentService,
    PortfolioSyncService,
)
from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort


class PortfolioProvider:
    def __init__(
        self,
        sync_service: PortfolioSyncService,
        repository: PortfolioProjectsRepositoryPort,
        enrichment_service: PortfolioEnrichmentService,
        citation_service: PortfolioCitationService,
    ) -> None:
        self._sync_service = sync_service
        self._repository = repository
        self._enrichment_service = enrichment_service
        self._citation_service = citation_service

    def get_sync_service(self) -> PortfolioSyncService:
        return self._sync_service

    def get_repository(self) -> PortfolioProjectsRepositoryPort:
        return self._repository

    def get_enrichment_service(self) -> PortfolioEnrichmentService:
        return self._enrichment_service

    def get_citation_service(self) -> PortfolioCitationService:
        return self._citation_service

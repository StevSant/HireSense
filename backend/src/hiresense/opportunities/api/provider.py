from __future__ import annotations

from hiresense.opportunities.domain.services import OpportunityIngestionService


class OpportunitiesProvider:
    def __init__(self, service: OpportunityIngestionService) -> None:
        self._service = service

    def get_service(self) -> OpportunityIngestionService:
        return self._service

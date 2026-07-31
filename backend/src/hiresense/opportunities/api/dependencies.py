from __future__ import annotations

from fastapi import Request

from hiresense.opportunities.domain.services import OpportunityIngestionService


def get_opportunities_service(request: Request) -> OpportunityIngestionService:
    return request.app.state.opportunities.get_service()

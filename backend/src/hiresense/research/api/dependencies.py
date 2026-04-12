from __future__ import annotations

from fastapi import Request

from hiresense.research.domain import CompanyResearchService


def get_company_research_service(request: Request) -> CompanyResearchService:
    return request.app.state.research.get_research_service()

from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from hiresense.identity.api.dependencies import enforce_expensive_rate_limit, require_auth
from hiresense.research.api.dependencies import get_company_research_service
from hiresense.research.api.schemas import CompanyResearchResponse, ResearchRequest
from hiresense.research.domain import logo_url as build_logo_url
from hiresense.research.domain.models import CompanyResearch
from hiresense.research.domain.services import CompanyResearchService

# Every route here can trigger LLM + external-HTTP generation (GET is get-or-create,
# POST/refresh always generate), so the whole router is behind the shared
# expensive-operation rate limit in addition to auth.
router = APIRouter(
    prefix="/research",
    tags=["research"],
    dependencies=[Depends(require_auth), Depends(enforce_expensive_rate_limit)],
)


def _to_response(result: CompanyResearch, request: Request) -> CompanyResearchResponse:
    """Build the response and attach the derived logo_url. Tolerates the router
    being mounted without app.state.settings (e.g. unit tests on a bare app)."""
    settings = getattr(request.app.state, "settings", None)
    service_url = getattr(settings, "logo_service_url", "") or ""
    resp = CompanyResearchResponse.model_validate(result)
    return resp.model_copy(update={"logo_url": build_logo_url(result.website, service_url)})


@router.post("", response_model=CompanyResearchResponse)
async def research_company(
    payload: ResearchRequest,
    request: Request,
    service: CompanyResearchService = Depends(get_company_research_service),
) -> CompanyResearchResponse:
    result = await service.research(
        company_name=payload.company_name, job_description=payload.job_description
    )
    return _to_response(result, request)


@router.post("/refresh", response_model=CompanyResearchResponse)
async def refresh_research(
    payload: ResearchRequest,
    request: Request,
    service: CompanyResearchService = Depends(get_company_research_service),
) -> CompanyResearchResponse:
    result = await service.refresh(
        company_name=payload.company_name, job_description=payload.job_description
    )
    return _to_response(result, request)


@router.get("/{company_name}", response_model=CompanyResearchResponse)
async def get_research(
    company_name: str,
    request: Request,
    service: CompanyResearchService = Depends(get_company_research_service),
) -> CompanyResearchResponse:
    result = await service.get_or_create(company_name)
    return _to_response(result, request)

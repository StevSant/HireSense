from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from hiresense.identity.api.dependencies import require_auth
from hiresense.research.api.dependencies import get_company_research_service
from hiresense.research.api.schemas import CompanyResearchResponse, ResearchRequest
from hiresense.research.domain.services import CompanyResearchService

router = APIRouter(prefix="/research", tags=["research"], dependencies=[Depends(require_auth)])


@router.post("", response_model=CompanyResearchResponse)
async def research_company(
    request: ResearchRequest,
    service: CompanyResearchService = Depends(get_company_research_service),
) -> CompanyResearchResponse:
    result = await service.research(
        company_name=request.company_name, job_description=request.job_description
    )
    return CompanyResearchResponse.model_validate(result)


@router.post("/refresh", response_model=CompanyResearchResponse)
async def refresh_research(
    request: ResearchRequest,
    service: CompanyResearchService = Depends(get_company_research_service),
) -> CompanyResearchResponse:
    result = await service.refresh(
        company_name=request.company_name, job_description=request.job_description
    )
    return CompanyResearchResponse.model_validate(result)


@router.get("/{company_name}", response_model=CompanyResearchResponse)
def get_research(
    company_name: str,
    service: CompanyResearchService = Depends(get_company_research_service),
) -> CompanyResearchResponse:
    result = service.get(company_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No research found for {company_name}")
    return CompanyResearchResponse.model_validate(result)

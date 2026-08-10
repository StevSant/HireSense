from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from hiresense.identity.api.dependencies import require_auth
from hiresense.kernel import resolve_page_limit
from hiresense.opportunities.api.dependencies import get_opportunities_service
from hiresense.opportunities.api.schemas import (
    FetchOpportunitiesResponse,
    OpportunityResponse,
    PaginatedOpportunitiesResponse,
)
from hiresense.opportunities.domain.models import OpportunityKind
from hiresense.opportunities.domain.services import OpportunityIngestionService
from hiresense.profile.api.dependencies import get_profile_service
from hiresense.profile.domain.services import ProfileService

router = APIRouter(
    prefix="/opportunities",
    tags=["opportunities"],
    dependencies=[Depends(require_auth)],
)

# Fallbacks when the router is mounted without app.state.settings (bare-app unit
# tests). Match the config defaults in config/groups/opportunities.py.
_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 100


def _page_size(request: Request, page_size: int | None) -> int:
    settings = getattr(request.app.state, "settings", None)
    return resolve_page_limit(
        page_size,
        default=(
            settings.opportunities_default_page_size if settings is not None else _DEFAULT_PAGE_SIZE
        ),
        maximum=(settings.opportunities_max_page_size if settings is not None else _MAX_PAGE_SIZE),
    )


async def _candidate_skills(profile_service: ProfileService) -> list[str]:
    skills: list[str] = []
    for profile in await profile_service.list_profiles():
        skills.extend(profile.skills or [])
    return skills


@router.get("", response_model=PaginatedOpportunitiesResponse)
async def list_opportunities(
    request: Request,
    kind: OpportunityKind | None = None,
    topic: str | None = None,
    topics: Annotated[list[str] | None, Query()] = None,
    exclude_topics: Annotated[list[str] | None, Query()] = None,
    country: str | None = None,
    q: str | None = None,
    funded_only: bool = False,
    deadline_before: date | None = None,
    deadline_after: date | None = None,
    hide_stale: bool = True,
    matched_only: bool = True,
    status: str = "open",
    sort: str = "match_desc",
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
    service: OpportunityIngestionService = Depends(get_opportunities_service),
    profile_service: ProfileService = Depends(get_profile_service),
) -> PaginatedOpportunitiesResponse:
    limit = _page_size(request, page_size)
    offset = (page - 1) * limit
    skills = await _candidate_skills(profile_service)
    # Without a profile, matched_only would hide almost nothing useful — keep feed browsable.
    effective_matched = matched_only and bool(skills)
    scored = service.list(
        kind=kind,
        topic=topic,
        topics=topics,
        exclude_topics=exclude_topics,
        country=country,
        q=q,
        funded_only=funded_only,
        deadline_before=deadline_before,
        deadline_after=deadline_after,
        hide_stale=hide_stale,
        status=status,
        sort=sort,
        matched_only=effective_matched,
        candidate_skills=skills,
        limit=limit,
        offset=offset,
    )
    total = service.count(
        kind=kind,
        topic=topic,
        topics=topics,
        exclude_topics=exclude_topics,
        country=country,
        q=q,
        funded_only=funded_only,
        deadline_before=deadline_before,
        deadline_after=deadline_after,
        hide_stale=hide_stale,
        status=status,
        matched_only=effective_matched,
        candidate_skills=skills,
    )
    items = [
        OpportunityResponse.model_validate(
            {
                **opp.model_dump(),
                "relevance_score": score,
            }
        )
        for opp, score in scored
    ]
    return PaginatedOpportunitiesResponse(
        items=items,
        total=total,
        page=page,
        page_size=limit,
    )


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(
    opportunity_id: uuid.UUID,
    service: OpportunityIngestionService = Depends(get_opportunities_service),
) -> OpportunityResponse:
    opp = service.get(opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return OpportunityResponse.model_validate(opp)


@router.post("/fetch", response_model=FetchOpportunitiesResponse)
async def fetch_opportunities(
    service: OpportunityIngestionService = Depends(get_opportunities_service),
) -> FetchOpportunitiesResponse:
    summary = await service.run()
    return FetchOpportunitiesResponse.model_validate(summary)

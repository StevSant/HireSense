from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from hiresense.identity.api.dependencies import enforce_expensive_rate_limit, require_auth
from hiresense.portfolio.api.dependencies import (
    get_engagement_service,
    get_projects_repository,
    get_sync_service,
)
from hiresense.portfolio.domain import (
    PortfolioEngagementService,
    PortfolioProject,
    PortfolioSyncService,
    PortfolioVisit,
    SyncResult,
)
from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort

router = APIRouter(prefix="/portfolio", tags=["portfolio"], dependencies=[Depends(require_auth)])


class ProjectsResponse(BaseModel):
    projects: list[PortfolioProject]
    last_synced_at: datetime | None


@router.post(
    "/sync", response_model=SyncResult, dependencies=[Depends(enforce_expensive_rate_limit)]
)
async def sync_portfolio(
    service: Annotated[PortfolioSyncService | None, Depends(get_sync_service)],
) -> SyncResult:
    if service is None:
        raise HTTPException(status_code=503, detail="No portfolio sources configured")
    result = await service.sync()
    if result.errors and not result.counts_by_source:
        raise HTTPException(
            status_code=502, detail=f"All portfolio sources failed: {result.errors}"
        )
    return result


@router.get("/projects", response_model=ProjectsResponse)
async def list_projects(
    repository: Annotated[
        PortfolioProjectsRepositoryPort | None, Depends(get_projects_repository)
    ],
) -> ProjectsResponse:
    if repository is None:
        return ProjectsResponse(projects=[], last_synced_at=None)
    projects = await asyncio.to_thread(repository.list_all)
    last = await asyncio.to_thread(repository.last_synced_at)
    return ProjectsResponse(projects=projects, last_synced_at=last)


class EngagementResponse(BaseModel):
    configured: bool
    visits: list[PortfolioVisit]


@router.get("/engagement", response_model=EngagementResponse)
async def get_engagement(
    service: Annotated[PortfolioEngagementService | None, Depends(get_engagement_service)],
) -> EngagementResponse:
    if service is None:
        return EngagementResponse(configured=False, visits=[])
    return EngagementResponse(configured=True, visits=await service.visits())

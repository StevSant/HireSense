from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from hiresense.ingestion.api.dependencies import (
    get_ingestion_orchestrator,
    get_portal_scanner,
    get_portals_config,
    get_semantic_scoring,
)
from hiresense.ingestion.domain.job_filter import JobQueryParams, PaginatedResult, filter_and_paginate
from hiresense.ingestion.domain.job_scorer import combine_fit_score, score_jobs
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner, ScanFilters, ScanResult
from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService
from hiresense.ingestion.domain.services import IngestionCooldownError, IngestionOrchestrator
from hiresense.profile.api.dependencies import get_profile_service
from hiresense.profile.domain import ProfileService

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class FetchResponse(BaseModel):
    count: int
    jobs: list[NormalizedJob]


@router.post("/fetch", response_model=FetchResponse)
async def fetch_jobs(
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
) -> FetchResponse | JSONResponse:
    try:
        jobs = await orchestrator.run()
    except IngestionCooldownError as exc:
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc), "retry_after": exc.retry_after},
            headers={"Retry-After": str(exc.retry_after)},
        )
    return FetchResponse(count=len(jobs), jobs=jobs)


@router.post("/scan-portals", response_model=ScanResult)
async def scan_portals(
    filters: ScanFilters,
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
) -> ScanResult:
    return await scanner.scan(filters)


@router.get("/jobs", response_model=PaginatedResult)
async def list_jobs(
    tab: Annotated[Literal["boards", "portals"], Query()],
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    semantic_scoring: Annotated[SemanticScoringService | None, Depends(get_semantic_scoring)],
    page: int = 1,
    page_size: int = 20,
    source: str | None = None,
    keyword: str | None = None,
    location: str | None = None,
    skills: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_location: str | None = None,
    strict_location: bool = False,
    sort: str | None = None,
) -> PaginatedResult:
    all_jobs = orchestrator.list_jobs() if tab == "boards" else scanner.list_jobs()

    candidate_skills: list[str] = []
    candidate_summary_parts: list[str] = []
    for profile in await profile_service.list_profiles():
        candidate_skills.extend(profile.skills)
        for section in profile.sections:
            candidate_summary_parts.append(section.content)
    candidate_summary = "\n".join(candidate_summary_parts)

    if candidate_skills:
        all_jobs = score_jobs(all_jobs, candidate_skills)

    params = JobQueryParams(
        page=page,
        page_size=page_size,
        source=source,
        keyword=keyword,
        location=location,
        skills=skills,
        date_from=date_from,
        date_to=date_to,
        user_location=user_location,
        strict_location=strict_location,
        sort=sort,
    )
    result = filter_and_paginate(all_jobs, params)

    # Semantic scoring is bounded to the visible page so the first request
    # after a backend restart doesn't block on 1000+ embeddings. Subsequent
    # pages incrementally warm the cache; the per-job cache persists for
    # the lifetime of the process.
    if (
        semantic_scoring is not None
        and (candidate_skills or candidate_summary)
        and result.jobs
    ):
        scored_page = await semantic_scoring.score_jobs(
            result.jobs, candidate_skills, candidate_summary
        )
        result.jobs = [
            j.model_copy(update={"match_score": combine_fit_score(j.match_score, j.semantic_score)})
            for j in scored_page
        ]

    return result


@router.get("/jobs/{job_id}", response_model=NormalizedJob)
async def get_job(
    job_id: str,
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
) -> NormalizedJob:
    job = orchestrator.get_job_by_id(job_id)
    if job is None:
        for j in scanner.list_jobs():
            if j.id == job_id:
                job = j
                break
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/portals", response_model=list[PortalEntry])
async def list_portals(
    config: Annotated[PortalsConfig, Depends(get_portals_config)],
) -> list[PortalEntry]:
    return config.portals

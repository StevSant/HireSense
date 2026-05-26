from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from hiresense.ingestion.api.dependencies import (
    get_ingestion_orchestrator,
    get_portal_scanner,
    get_portals_config,
    get_semantic_scoring,
)
from hiresense.ingestion.domain.job_filter import JobQueryParams, PaginatedResult, filter_and_paginate
from hiresense.ingestion.domain.job_scorer import (
    combine_fit_score,
    score_job_against_skills,
    score_jobs,
)
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.seniority import SeniorityLevel
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
    request: Request,
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
    min_score: float | None = None,
    seniority: Annotated[list[SeniorityLevel] | None, Query()] = None,
    max_years_experience: int | None = None,
) -> PaginatedResult:
    # Default min_score from settings when the client doesn't specify one
    # (pass min_score=0 explicitly to disable the filter). Tests mount the
    # router on a bare FastAPI without app.state.settings — fall back to
    # no-filter in that case.
    if min_score is None:
        settings = getattr(request.app.state, "settings", None)
        if settings is not None:
            min_score = settings.ingestion_min_match_score
    all_jobs = orchestrator.list_jobs() if tab == "boards" else scanner.list_jobs()

    candidate_skills: list[str] = []
    candidate_summary_parts: list[str] = []
    for profile in await profile_service.list_profiles():
        candidate_skills.extend(profile.skills)
        for section in profile.sections:
            candidate_summary_parts.append(section.content)
    candidate_summary = "\n".join(candidate_summary_parts)

    persist_scores = orchestrator.persist_scores if tab == "boards" else scanner.persist_scores

    # Pre-compute skill-overlap per job (cheap) and fold in any *persisted*
    # semantic score so the sort key matches the displayed value. Keep the
    # raw skill score in a side dict so we can re-combine after page-level
    # semantic scoring without recomputing the overlap.
    skill_by_id: dict[str, float | None] = {}
    if candidate_skills:
        skill_set = {s.lower() for s in candidate_skills if s}
        for job in all_jobs:
            skill_by_id[job.id] = score_job_against_skills(job, skill_set)
        all_jobs = [
            j.model_copy(
                update={"match_score": combine_fit_score(skill_by_id[j.id], j.semantic_score)}
            )
            for j in all_jobs
        ]
        for job in all_jobs:
            persist_scores(job.id, job.match_score, job.semantic_score)

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
        min_score=min_score,
        seniority_levels=seniority,
        max_years_experience=max_years_experience,
    )
    result = filter_and_paginate(all_jobs, params)

    # Semantic scoring is bounded to the visible page so the first request
    # after a backend restart doesn't block on 1000+ embeddings. Each request
    # only computes semantic for jobs on this page that don't yet have one;
    # the persisted score feeds back into the sort on subsequent calls.
    needs_semantic = [j for j in result.jobs if j.semantic_score is None]
    if (
        semantic_scoring is not None
        and (candidate_skills or candidate_summary)
        and needs_semantic
    ):
        scored = await semantic_scoring.score_jobs(
            needs_semantic, candidate_skills, candidate_summary
        )
        scored_by_id = {j.id: j.semantic_score for j in scored}
        result.jobs = [
            j.model_copy(
                update={
                    "semantic_score": scored_by_id.get(j.id, j.semantic_score),
                }
            )
            for j in result.jobs
        ]
        # Re-combine match_score using the skill side dict + fresh semantic.
        result.jobs = [
            j.model_copy(
                update={
                    "match_score": combine_fit_score(
                        skill_by_id.get(j.id), j.semantic_score
                    )
                }
            )
            for j in result.jobs
        ]
        for job in result.jobs:
            persist_scores(job.id, job.match_score, job.semantic_score)
        # Page-level re-sort so the order reflects the post-semantic match_score
        # that the user actually sees. Phase-1 sort happens pre-pagination on
        # skill-only scores; without this the displayed % column looks unsorted.
        if sort == "match_desc":
            result.jobs = sorted(
                result.jobs,
                key=lambda j: (j.match_score if j.match_score is not None else -1.0),
                reverse=True,
            )

    return result


@router.get("/jobs/{job_id}", response_model=NormalizedJob)
async def get_job(
    job_id: str,
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
) -> NormalizedJob:
    job = orchestrator.get_job_by_id(job_id) or scanner.get_job_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/portals", response_model=list[PortalEntry])
async def list_portals(
    config: Annotated[PortalsConfig, Depends(get_portals_config)],
) -> list[PortalEntry]:
    return config.portals

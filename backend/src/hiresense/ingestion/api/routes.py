from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from hiresense.identity.api.dependencies import enforce_expensive_rate_limit, require_auth
from hiresense.ingestion.api.job_feed_service import DeepAnalysisUnavailableError, JobFeedService
from hiresense.ingestion.api.dependencies import (
    get_backfill_service,
    get_ingestion_orchestrator,
    get_job_feed,
    get_portal_scanner,
    get_portals_config,
    get_revalidation_service,
)
from hiresense.ingestion.domain.embedding_backfill_service import EmbeddingBackfillService
from hiresense.ingestion.domain.job_filter import (
    PaginatedResult,
)
from hiresense.ingestion.domain.job_revalidation_service import JobRevalidationService
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner, ScanFilters, ScanResult
from hiresense.ingestion.domain.seniority import SeniorityLevel
from hiresense.ingestion.domain.services import IngestionCooldownError, IngestionOrchestrator
from hiresense.ingestion.domain.source_capabilities import (
    SourceCapabilities,
    list_source_capabilities,
)
from hiresense.ingestion.domain.source_health import SourceHealth
from hiresense.matching.domain.deep_analysis_result import DeepAnalysisResult

router = APIRouter(prefix="/ingestion", tags=["ingestion"], dependencies=[Depends(require_auth)])


# Accepted sort tokens (`<field>_<dir>`) plus the legacy `date_*` aliases. Any
# value outside this set falls back to the default `match_desc`.
class FetchResponse(BaseModel):
    count: int
    jobs: list[NormalizedJob]


class SourceInfo(BaseModel):
    capabilities: SourceCapabilities
    enabled: bool
    wired: bool


class SourcesResponse(BaseModel):
    sources: list[SourceInfo]


class SourcesHealthResponse(BaseModel):
    sources: list[SourceHealth]


@router.get("/sources", response_model=SourcesResponse)
async def list_sources(
    request: Request,
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
) -> SourcesResponse:
    """Capability registry + enablement for board sources."""
    settings = getattr(request.app.state, "settings", None)
    enabled = set(getattr(settings, "enabled_job_sources", []) or [])
    wired = set(orchestrator.source_names())
    items: list[SourceInfo] = []
    for caps in list_source_capabilities():
        items.append(
            SourceInfo(
                capabilities=caps,
                enabled=caps.source in enabled,
                wired=caps.source in wired,
            )
        )
    return SourcesResponse(sources=items)


@router.get("/sources/health", response_model=SourcesHealthResponse)
async def sources_health(
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
) -> SourcesHealthResponse:
    return SourcesHealthResponse(sources=orchestrator.health_tracker.snapshot())


@router.post(
    "/fetch", response_model=FetchResponse, dependencies=[Depends(enforce_expensive_rate_limit)]
)
async def fetch_jobs(
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
    revalidation: Annotated[JobRevalidationService | None, Depends(get_revalidation_service)],
    background_tasks: BackgroundTasks,
) -> FetchResponse | JSONResponse:
    try:
        jobs = await orchestrator.run()
    except IngestionCooldownError as exc:
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc), "retry_after": exc.retry_after},
            headers={"Retry-After": str(exc.retry_after)},
        )
    # User-initiated fetch also kicks off a bounded URL-probe revalidation sweep
    # so dead feed/search listings (incl. hn_hiring "Sorry." pages) get closed
    # without depending solely on the external cron. Runs AFTER the response is
    # sent (BackgroundTasks) since the sweep is throttled and can take a while;
    # this is request-scoped work, not app self-scheduling.
    if revalidation is not None:
        background_tasks.add_task(revalidation.sweep)
    return FetchResponse(count=len(jobs), jobs=jobs)


@router.post(
    "/scan-portals", response_model=ScanResult, dependencies=[Depends(enforce_expensive_rate_limit)]
)
async def scan_portals(
    filters: ScanFilters,
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
) -> ScanResult:
    return await scanner.scan(filters)


class RevalidationRequest(BaseModel):
    # The jobs currently on screen. When present, they're probed synchronously
    # for an immediate result, and a full-corpus sweep is also kicked off in the
    # background for everything else.
    job_ids: list[str] | None = None


class RevalidationResponse(BaseModel):
    # `started` is True whenever a sweep was triggered. `closed`/`closed_ids`
    # report the SYNCHRONOUS portion (the targeted job_ids, or a synchronous
    # full run); a backgrounded full sweep continues after the response and its
    # closures surface on subsequent list reloads.
    started: bool = True
    closed: int = 0
    closed_ids: list[str] = []


class RevalidationStatusResponse(BaseModel):
    """Progress of the background sweep, so the UI can show a real ratio and
    clear its banner on completion instead of claiming work forever."""

    sweeping: bool
    checked: int
    total: int
    closed: int


@router.get("/revalidate/status", response_model=RevalidationStatusResponse)
async def revalidation_status(
    service: Annotated[JobRevalidationService | None, Depends(get_revalidation_service)],
) -> RevalidationStatusResponse:
    """Cheap, poll-friendly snapshot: reads in-memory counters, touches no DB.

    Deliberately NOT rate-limited alongside the expensive endpoints — it exists
    to be polled while a sweep of thousands of listings runs for tens of minutes.
    """
    if service is None:
        raise HTTPException(status_code=503, detail="Revalidation is not configured")
    return RevalidationStatusResponse(**service.progress())


@router.post("/revalidate", response_model=RevalidationResponse)
async def revalidate_jobs(
    service: Annotated[JobRevalidationService | None, Depends(get_revalidation_service)],
    background_tasks: BackgroundTasks,
    body: RevalidationRequest | None = None,
    background: bool = False,
) -> RevalidationResponse:
    """Probe open feed/search jobs across all platforms and close the dead ones
    (gone / "no longer accepting applications").

    - With `job_ids` (the UI's "Check closed" button): probe those jobs NOW and
      return their closures immediately, AND kick off a full-corpus background
      sweep for the rest.
    - With `background=true` and no ids: schedule only the full background sweep.
    - Otherwise (external cron): run the full sweep synchronously and report the
      closed count.

    Snapshot sources (portals) rely on disappearance detection during ingestion
    instead.
    """
    if service is None:
        raise HTTPException(status_code=503, detail="Revalidation is not configured")
    if body is not None and body.job_ids is not None:
        # Button path — probe the visible jobs now (empty list = nothing to probe)
        # and sweep the rest in the background. Keyed on presence, not truthiness,
        # so an empty visible page still backgrounds instead of blocking on a
        # synchronous full sweep.
        closed = await service.revalidate_ids(body.job_ids)
        background_tasks.add_task(service.sweep)
        return RevalidationResponse(started=True, closed=len(closed), closed_ids=closed)
    if background:
        background_tasks.add_task(service.sweep)
        return RevalidationResponse(started=True)
    closed = await service.sweep()
    return RevalidationResponse(started=True, closed=len(closed), closed_ids=closed)


@router.get(
    "/jobs", response_model=PaginatedResult, dependencies=[Depends(enforce_expensive_rate_limit)]
)
async def list_jobs(
    feed: Annotated[JobFeedService, Depends(get_job_feed)],
    tab: Annotated[Literal["boards", "portals", "all"], Query()],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1)] = 20,
    source: str | None = None,
    company: str | None = None,
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
    include_closed: bool = False,
    rescore: bool = True,
    max_age_days: int | None = None,
    include_low_quality: bool = False,
) -> PaginatedResult:
    return await feed.list_jobs(
        tab=tab,
        page=page,
        page_size=page_size,
        source=source,
        company=company,
        keyword=keyword,
        location=location,
        skills=skills,
        date_from=date_from,
        date_to=date_to,
        user_location=user_location,
        strict_location=strict_location,
        sort=sort,
        min_score=min_score,
        seniority=seniority,
        max_years_experience=max_years_experience,
        include_closed=include_closed,
        rescore=rescore,
        max_age_days=max_age_days,
        include_low_quality=include_low_quality,
    )


@router.get(
    "/jobs/{job_id}/analysis",
    response_model=DeepAnalysisResult,
    dependencies=[Depends(enforce_expensive_rate_limit)],
)
async def analyze_job(
    job_id: str,
    feed: Annotated[JobFeedService, Depends(get_job_feed)],
    force: bool = False,
) -> DeepAnalysisResult:
    """Deep, single-job match analysis (advanced model, cached, on demand)."""
    try:
        result = await feed.analyze_job(job_id, force=force)
    except DeepAnalysisUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@router.get("/jobs/{job_id}", response_model=NormalizedJob)
async def get_job(
    job_id: str,
    feed: Annotated[JobFeedService, Depends(get_job_feed)],
) -> NormalizedJob:
    job = await feed.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/portals", response_model=list[PortalEntry])
async def list_portals(
    config: Annotated[PortalsConfig, Depends(get_portals_config)],
) -> list[PortalEntry]:
    return config.portals


class BackfillResponse(BaseModel):
    boards: int
    portals: int
    total: int


@router.post(
    "/backfill-embeddings",
    response_model=BackfillResponse,
    dependencies=[Depends(enforce_expensive_rate_limit)],
)
async def backfill_embeddings(
    service: Annotated[EmbeddingBackfillService | None, Depends(get_backfill_service)],
) -> BackfillResponse:
    """Re-embed all ingested jobs into pgvector so SemanticPreRanker can rank them.

    Idempotent: re-running replaces existing vectors in place. Safe to trigger
    multiple times without duplicating entries. Returns per-bucket counts of
    jobs successfully indexed.
    """
    if service is None:
        raise HTTPException(status_code=503, detail="Embedding backfill is not configured")
    result = await service.run()
    return BackfillResponse(boards=result.boards, portals=result.portals, total=result.total)

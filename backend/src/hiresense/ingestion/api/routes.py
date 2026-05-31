from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from hiresense.identity.api.dependencies import require_auth
from hiresense.ingestion.api.dependencies import (
    get_backfill_service,
    get_deep_analysis,
    get_ingestion_orchestrator,
    get_portal_scanner,
    get_portals_config,
    get_pre_ranker,
    get_quick_scoring,
    get_revalidation_service,
    get_semantic_scoring,
)
from hiresense.ingestion.domain.embedding_backfill_service import EmbeddingBackfillService
from hiresense.ingestion.domain.job_filter import JobQueryParams, PaginatedResult, filter_and_paginate
from hiresense.ingestion.domain.job_revalidation_service import JobRevalidationService
from hiresense.ingestion.domain.job_scorer import (
    combine_fit_score,
    score_job_against_skills,
)
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner, ScanFilters, ScanResult
from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
from hiresense.ingestion.domain.quick_scoring_service import QuickScoringService
from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker
from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService
from hiresense.ingestion.domain.seniority import SeniorityLevel
from hiresense.ingestion.domain.services import IngestionCooldownError, IngestionOrchestrator
from hiresense.ingestion.ports.jobs_repository import ScoreUpdate
from hiresense.matching.domain.deep_analysis_result import DeepAnalysisResult
from hiresense.matching.domain.deep_analysis_service import DeepAnalysisService
from hiresense.profile.api.dependencies import get_profile_service
from hiresense.profile.domain import ProfileService

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


async def _gather_profile(profile_service: ProfileService) -> tuple[list[str], str]:
    """Flatten all stored profiles into candidate skills + a summary blob.

    Shared by the list endpoint (quick scoring) and the analysis endpoint
    (deep scoring) so both score against the same profile representation.
    """
    candidate_skills: list[str] = []
    summary_parts: list[str] = []
    for profile in await profile_service.list_profiles():
        candidate_skills.extend(profile.skills)
        for section in profile.sections:
            summary_parts.append(section.content)
    return candidate_skills, "\n".join(summary_parts)


def _apply_quick(job: NormalizedJob, quick: QuickMatchResult | None) -> NormalizedJob:
    """Overlay an LLM quick result onto a job for the response.

    The displayed `match_score` becomes the LLM score (more accurate than the
    heuristic), and the quick verdict/reasons/dealbreakers ride along for the
    detail panel. Jobs without a quick result keep their heuristic score.
    """
    if quick is None:
        return job
    return job.model_copy(
        update={
            "match_score": quick.score,
            "llm_score": quick.score,
            "verdict": quick.verdict.value,
            "reasons": list(quick.reasons),
            "dealbreakers": list(quick.dealbreakers),
        }
    )


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


class RevalidationResponse(BaseModel):
    closed: int


@router.post("/revalidate", response_model=RevalidationResponse)
async def revalidate_jobs(
    service: Annotated[JobRevalidationService | None, Depends(get_revalidation_service)],
) -> RevalidationResponse:
    """Trigger one URL-probe revalidation sweep (intended for an external cron).

    Closes feed/search jobs whose listing is gone or marked closed. Snapshot
    sources (portals) rely on disappearance detection during ingestion instead.
    """
    if service is None:
        raise HTTPException(status_code=503, detail="Revalidation is not configured")
    closed = await service.sweep()
    return RevalidationResponse(closed=len(closed))


@router.get("/jobs", response_model=PaginatedResult)
async def list_jobs(
    request: Request,
    tab: Annotated[Literal["boards", "portals"], Query()],
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    semantic_scoring: Annotated[SemanticScoringService | None, Depends(get_semantic_scoring)],
    quick_scoring: Annotated[QuickScoringService | None, Depends(get_quick_scoring)],
    pre_ranker: Annotated[SemanticPreRanker | None, Depends(get_pre_ranker)],
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
    include_closed: bool = False,
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

    candidate_skills, candidate_summary = await _gather_profile(profile_service)

    persist_scores_batch = (
        orchestrator.persist_scores_batch if tab == "boards" else scanner.persist_scores_batch
    )

    # Default to match-descending so the ranking is actually applied when the
    # client omits sort (otherwise the page reflects insertion order — #18).
    effective_sort = sort or "match_desc"

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

    # GLOBAL pre-rank BEFORE pagination (#18 fix): use the pgvector ANN to set
    # semantic_score + combined match_score across the WHOLE corpus, so a
    # high-semantic / low-keyword job can reach page 1 instead of being scored
    # only after it's already been paginated off. Passthrough (no vector store,
    # empty profile, etc.) leaves the skill-only ordering intact.
    if pre_ranker is not None:
        all_jobs = await pre_ranker.rerank(
            all_jobs, skill_by_id, candidate_skills, candidate_summary, bucket=tab
        )

    if candidate_skills:
        persist_scores_batch(
            [ScoreUpdate(j.id, j.match_score, j.semantic_score) for j in all_jobs]
        )

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
        sort=effective_sort,
        min_score=min_score,
        seniority_levels=seniority,
        max_years_experience=max_years_experience,
        include_closed=include_closed,
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
        persist_scores_batch(
            [ScoreUpdate(j.id, j.match_score, j.semantic_score) for j in result.jobs]
        )
        # Page-level re-sort so the order reflects the post-semantic match_score
        # that the user actually sees. Phase-1 sort happens pre-pagination on
        # skill-only scores; without this the displayed % column looks unsorted.
        if effective_sort == "match_desc":
            result.jobs = sorted(
                result.jobs,
                key=lambda j: (j.match_score if j.match_score is not None else -1.0),
                reverse=True,
            )

    # Tier-1 LLM quick scoring of the visible page (cheap model, one batched
    # call, cached per (job_id, profile_hash)). Runs *after* pagination so the
    # min_score gate never culls a job on a not-yet-computed LLM score. The LLM
    # score replaces the displayed match_score when available; jobs without one
    # keep the heuristic blend. Cache hits make repeat views instant.
    if quick_scoring is not None and (candidate_skills or candidate_summary):
        quick_results = await quick_scoring.score_page(
            result.jobs, candidate_skills, candidate_summary
        )
        if quick_results:
            result.jobs = [_apply_quick(j, quick_results.get(j.id)) for j in result.jobs]
            if effective_sort == "match_desc":
                result.jobs = sorted(
                    result.jobs,
                    key=lambda j: (j.match_score if j.match_score is not None else -1.0),
                    reverse=True,
                )

    return result


@router.get("/jobs/{job_id}/analysis", response_model=DeepAnalysisResult)
async def analyze_job(
    job_id: str,
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    deep_analysis: Annotated[DeepAnalysisService | None, Depends(get_deep_analysis)],
    force: bool = False,
) -> DeepAnalysisResult:
    """Deep, single-job match analysis (advanced model, cached, on demand)."""
    job = orchestrator.get_job_by_id(job_id) or scanner.get_job_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if deep_analysis is None:
        raise HTTPException(status_code=503, detail="Deep analysis is not available")
    candidate_skills, candidate_summary = await _gather_profile(profile_service)
    return await deep_analysis.analyze(
        job, candidate_skills, candidate_summary, force=force
    )


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


class BackfillResponse(BaseModel):
    boards: int
    portals: int
    total: int


@router.post("/backfill-embeddings", response_model=BackfillResponse)
async def backfill_embeddings(
    # The authenticated user IS the operator — this is a single-user app with
    # no role system. require_auth verifies the JWT and returns the subject claim.
    _operator: Annotated[str, Depends(require_auth)],
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

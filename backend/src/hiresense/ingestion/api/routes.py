from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from hiresense.identity.api.dependencies import enforce_expensive_rate_limit, require_auth
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
from hiresense.ingestion.domain.job_list_criteria import JobListCriteria
from hiresense.ingestion.domain.job_revalidation_service import JobRevalidationService
from hiresense.ingestion.domain.job_sort import sort_jobs
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

router = APIRouter(
    prefix="/ingestion", tags=["ingestion"], dependencies=[Depends(require_auth)]
)

# Accepted sort tokens (`<field>_<dir>`) plus the legacy `date_*` aliases. Any
# value outside this set falls back to the default `match_desc`.
_ALLOWED_SORTS = frozenset(
    f"{field}_{direction}"
    for field in ("match", "posted", "title", "company", "location", "source")
    for direction in ("asc", "desc")
) | {"date_desc", "date_asc"}


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


@router.post("/fetch", response_model=FetchResponse, dependencies=[Depends(enforce_expensive_rate_limit)])
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


@router.post("/scan-portals", response_model=ScanResult, dependencies=[Depends(enforce_expensive_rate_limit)])
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


@router.get("/jobs", response_model=PaginatedResult, dependencies=[Depends(enforce_expensive_rate_limit)])
async def list_jobs(
    request: Request,
    tab: Annotated[Literal["boards", "portals"], Query()],
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    semantic_scoring: Annotated[SemanticScoringService | None, Depends(get_semantic_scoring)],
    quick_scoring: Annotated[QuickScoringService | None, Depends(get_quick_scoring)],
    pre_ranker: Annotated[SemanticPreRanker | None, Depends(get_pre_ranker)],
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
    # Default min_score / max_age_days from settings when the client doesn't
    # specify them (pass 0 explicitly to disable either filter). Tests mount the
    # router on a bare FastAPI without app.state.settings — fall back to
    # no-filter in that case.
    settings = getattr(request.app.state, "settings", None)
    if min_score is None and settings is not None:
        min_score = settings.ingestion_min_match_score
    if max_age_days is None and settings is not None:
        max_age_days = settings.ingestion_max_job_age_days
    # Clamp page_size to the configured cap (bounds per-request memory and
    # quick-scoring cost). The cap lives in settings, so it can't be a static
    # Query(le=) bound.
    if settings is not None:
        page_size = min(page_size, settings.ingestion_max_page_size)
    # Push the cheap selective predicates into the repository (SQL WHERE) so
    # closed/filtered rows never reach the scoring pipeline below.
    # filter_and_paginate re-applies them idempotently alongside the
    # Python-only heuristics.
    criteria = JobListCriteria(
        include_closed=include_closed,
        include_low_quality=include_low_quality,
        source=source,
        company=company,
        date_from=date_from,
        date_to=date_to,
    )
    # Corpus load + score persists below run sync SQLAlchemy sessions; offload
    # to a worker thread so they don't block the event loop.
    all_jobs = await asyncio.to_thread(
        orchestrator.list_jobs if tab == "boards" else scanner.list_jobs, criteria
    )

    candidate_skills, candidate_summary = await _gather_profile(profile_service)

    persist_scores_batch = (
        orchestrator.persist_scores_batch if tab == "boards" else scanner.persist_scores_batch
    )

    # Default to match-descending so the ranking is actually applied when the
    # client omits sort (otherwise the page reflects insertion order — #18).
    effective_sort = sort or "match_desc"
    if effective_sort not in _ALLOWED_SORTS:
        effective_sort = "match_desc"

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
        await asyncio.to_thread(
            persist_scores_batch,
            [ScoreUpdate(j.id, j.match_score, j.semantic_score) for j in all_jobs],
        )

    # GLOBAL apply of already-cached Tier-1 LLM scores BEFORE pagination. The
    # LLM quick score is the accurate, displayed match value, but it was only
    # ever applied to the visible page — so the global sort ranked by the
    # heuristic blend, which is source-biased (hn_hiring scores via verbose
    # text-mention and saturates; getonboard's structured tags get dilution-
    # capped low). A genuinely strong job from a "weak-heuristic" source was
    # buried off page 1 and never LLM-scored in the all-sources view, even
    # though it ranked highly once its source was filtered.
    #
    # Reading the LLM cache (keyed by job_id+profile_hash, source-agnostic) for
    # the WHOLE corpus and overriding match_score where we have a score makes
    # the global ranking consistent with the displayed value across every
    # filter. This is cache-only (`llm_on_miss=False`) — no LLM calls, one bulk
    # read — so it's safe on the sort-only fast path too. Visible-page cache
    # misses are filled by the page-level pass below and improve later rankings.
    # Applied AFTER persist so the persisted row score stays the heuristic blend
    # (the LLM score lives in its own cache); this override is request-scoped.
    if quick_scoring is not None and (candidate_skills or candidate_summary):
        cached_quick = await quick_scoring.score_page(
            all_jobs, candidate_skills, candidate_summary, llm_on_miss=False
        )
        if cached_quick:
            all_jobs = [_apply_quick(j, cached_quick.get(j.id)) for j in all_jobs]

    params = JobQueryParams(
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
        sort=effective_sort,
        min_score=min_score,
        seniority_levels=seniority,
        max_years_experience=max_years_experience,
        include_closed=include_closed,
        max_age_days=max_age_days,
        include_low_quality=include_low_quality,
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
        await asyncio.to_thread(
            persist_scores_batch,
            [ScoreUpdate(j.id, j.match_score, j.semantic_score) for j in result.jobs],
        )
        # Page-level re-sort so the order reflects the post-semantic match_score
        # that the user actually sees. Phase-1 sort happens pre-pagination on
        # skill-only scores; without this the displayed % column looks unsorted.
        # Only match-field sorts depend on post-pagination scores; every other
        # field's order from filter_and_paginate is already final.
        if effective_sort.startswith("match_"):
            result.jobs = sort_jobs(result.jobs, effective_sort)

    # Tier-1 LLM quick scoring of the visible page (cheap model, one batched
    # call, cached per (job_id, profile_hash)). Runs *after* pagination so the
    # min_score gate never culls a job on a not-yet-computed LLM score. The LLM
    # score replaces the displayed match_score when available; jobs without one
    # keep the heuristic blend. Cache hits make repeat views instant.
    #
    # `rescore=False` is the sort-only / pagination fast path (#76): the result
    # set and order are already determined by the (cheap) skill + ANN + min_score
    # steps above, which still ran. We only DEFER the blocking LLM round-trip —
    # quick scoring runs cache-only (`llm_on_miss=False`), so a reorder reuses
    # already-computed scores instantly and newly-surfaced jobs show their
    # heuristic blend until the next full rescore fills the cache. Clients send
    # rescore=False only for pure reorder/pagination; any filter, tab, feedback
    # or fetch change keeps the default (full LLM scoring of the page).
    if quick_scoring is not None and (candidate_skills or candidate_summary):
        quick_results = await quick_scoring.score_page(
            result.jobs, candidate_skills, candidate_summary, llm_on_miss=rescore
        )
        if quick_results:
            result.jobs = [_apply_quick(j, quick_results.get(j.id)) for j in result.jobs]
            if effective_sort.startswith("match_"):
                result.jobs = sort_jobs(result.jobs, effective_sort)

    return result


@router.get("/jobs/{job_id}/analysis", response_model=DeepAnalysisResult, dependencies=[Depends(enforce_expensive_rate_limit)])
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


@router.post("/backfill-embeddings", response_model=BackfillResponse, dependencies=[Depends(enforce_expensive_rate_limit)])
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

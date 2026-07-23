from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from hiresense.identity.api.dependencies import enforce_expensive_rate_limit, require_auth
from hiresense.matching.api.dependencies import (
    get_batch_evaluation_service,
    get_ingestion_orchestrator_for_matching,
    get_matching_orchestrator,
    get_optional_profile_service,
    get_tracking_service_for_matching,
)
from hiresense.matching.api.schemas import (
    BatchEvaluateRequest,
    BatchEvaluationResponse,
    BatchResultResponse,
    DimensionResultResponse,
    EligibilityResponse,
    EvaluateRequest,
    EvaluationResponse,
)
from hiresense.matching.domain.models import MatchResult

router = APIRouter(prefix="/matching", tags=["matching"], dependencies=[Depends(require_auth)])


class AnalyzeRequest(BaseModel):
    job_id: str
    cv_id: str
    job_description: str
    job_skills: list[str]
    cv_summary: str
    cv_skills: list[str]
    cv_embedding: list[float] | None = None
    job_embedding: list[float] | None = None


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    dependencies=[Depends(enforce_expensive_rate_limit)],
)
async def evaluate_job(
    body: EvaluateRequest,
    orchestrator: Annotated[object, Depends(get_matching_orchestrator)],
    profile_service: Annotated[object | None, Depends(get_optional_profile_service)],
) -> EvaluationResponse:
    job = {
        "title": body.job_title or "",
        "company": body.company or "",
        "description": body.description or "",
        "skills": body.skills,
        "location": body.location or "",
        "requires_existing_work_authorization": body.requires_existing_work_authorization,
        "visa_sponsorship_available": body.visa_sponsorship_available,
    }
    profile = (
        await profile_service.get_profile(body.profile_id)
        if profile_service and body.profile_id
        else None
    )
    result = await orchestrator.evaluate(job=job, profile=profile)
    return EvaluationResponse(
        composite_score=result.composite_score,
        job_title=result.job_title,
        company=result.company,
        dimensions=[
            DimensionResultResponse(
                dimension=d.dimension, score=d.score, rationale=d.rationale, weight=d.weight
            )
            for d in result.dimensions
        ],
        eligibility=EligibilityResponse(
            status=result.eligibility.status,
            rationale=result.eligibility.rationale,
        ),
    )


@router.post(
    "/analyze", response_model=MatchResult, dependencies=[Depends(enforce_expensive_rate_limit)]
)
async def analyze_match(
    body: AnalyzeRequest,
    orchestrator: Annotated[object, Depends(get_matching_orchestrator)],
) -> MatchResult:
    return await orchestrator.analyze(
        job_id=body.job_id,
        cv_id=body.cv_id,
        job_description=body.job_description,
        job_skills=body.job_skills,
        cv_summary=body.cv_summary,
        cv_skills=body.cv_skills,
        cv_embedding=body.cv_embedding,
        job_embedding=body.job_embedding,
    )


@router.post(
    "/batch-evaluate",
    response_model=BatchEvaluationResponse,
    dependencies=[Depends(enforce_expensive_rate_limit)],
)
async def batch_evaluate(
    body: BatchEvaluateRequest,
    batch_service: Annotated[object, Depends(get_batch_evaluation_service)],
    tracking_service: Annotated[object, Depends(get_tracking_service_for_matching)],
    ingestion_orchestrator: Annotated[object, Depends(get_ingestion_orchestrator_for_matching)],
    profile_service: Annotated[object | None, Depends(get_optional_profile_service)],
) -> BatchEvaluationResponse:
    jobs: list[dict] = []

    if body.tracked_app_ids:
        for app_id in body.tracked_app_ids:
            try:
                app = tracking_service.get(app_id)
                jobs.append(
                    {
                        "title": app.title,
                        "company": app.company,
                        "description": getattr(app, "notes", "") or "",
                        "source": "tracked",
                        "source_id": str(app.id),
                    }
                )
            except ValueError:
                continue
    else:
        for app in tracking_service.list():
            jobs.append(
                {
                    "title": app.title,
                    "company": app.company,
                    "description": "",
                    "source": "tracked",
                    "source_id": str(app.id),
                }
            )

    if body.include_ingested:
        for job in ingestion_orchestrator.list_jobs():
            jobs.append(
                {
                    "title": job.title,
                    "company": job.company,
                    "description": getattr(job, "description", ""),
                    "skills": getattr(job, "skills", []),
                        "location": getattr(job, "location", ""),
                        "requires_existing_work_authorization": getattr(
                            job, "requires_existing_work_authorization", None
                        ),
                        "visa_sponsorship_available": getattr(
                            job, "visa_sponsorship_available", None
                        ),
                    "source": "ingested",
                    "source_id": str(job.id),
                }
            )

    profile = (
        await profile_service.get_profile(body.profile_id)
        if profile_service and body.profile_id
        else None
    )
    if profile is None:
        results = await batch_service.evaluate_batch(jobs)
    else:
        results = await batch_service.evaluate_batch(jobs, profile=profile)

    return BatchEvaluationResponse(
        total_jobs=len(results),
        results=[
            BatchResultResponse(
                job_title=r.job_title,
                company=r.company,
                source=r.source,
                source_id=r.source_id,
                composite_score=r.composite_score,
                dimensions=[
                    DimensionResultResponse(
                        dimension=d.dimension,
                        score=d.score,
                        rationale=d.rationale,
                        weight=d.weight,
                    )
                    for d in r.dimensions
                ],
                eligibility=EligibilityResponse(
                    status=r.eligibility.status,
                    rationale=r.eligibility.rationale,
                ),
                failed=r.failed,
            )
            for r in results
        ],
    )

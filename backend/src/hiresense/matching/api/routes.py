from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from hiresense.matching.api.dependencies import get_matching_orchestrator
from hiresense.matching.api.schemas import DimensionResultResponse, EvaluateRequest, EvaluationResponse
from hiresense.matching.domain.models import MatchResult

router = APIRouter(prefix="/matching", tags=["matching"])


class AnalyzeRequest(BaseModel):
    job_id: str
    cv_id: str
    job_description: str
    job_skills: list[str]
    cv_summary: str
    cv_skills: list[str]
    cv_embedding: list[float] | None = None
    job_embedding: list[float] | None = None


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_job(
    body: EvaluateRequest,
    orchestrator: Annotated[object, Depends(get_matching_orchestrator)],
) -> EvaluationResponse:
    job = {
        "title": body.job_title or "",
        "company": body.company or "",
        "description": body.description or "",
        "skills": body.skills,
        "location": body.location or "",
    }
    result = await orchestrator.evaluate(
        job=job, profile=None,
        dimension_scorers=getattr(orchestrator, "_dimension_scorers", []),
    )
    return EvaluationResponse(
        composite_score=result.composite_score,
        job_title=result.job_title,
        company=result.company,
        dimensions=[
            DimensionResultResponse(dimension=d.dimension, score=d.score, rationale=d.rationale, weight=d.weight)
            for d in result.dimensions
        ],
    )


@router.post("/analyze", response_model=MatchResult)
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

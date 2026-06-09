from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from hiresense.identity.api.dependencies import require_auth
from hiresense.optimization.api.dependencies import get_cv_optimizer
from hiresense.optimization.domain.models import OptimizationResult

router = APIRouter(
    prefix="/optimization", tags=["optimization"], dependencies=[Depends(require_auth)]
)


class OptimizeRequest(BaseModel):
    match_id: str
    job_id: str
    cv_id: str
    original_tex: str
    job_description: str
    job_skills: list[str]
    missing_skills: list[str] = []
    recommendations: list[str] = []


@router.post("/optimize", response_model=OptimizationResult)
async def optimize_cv(
    body: OptimizeRequest,
    optimizer: Annotated[object, Depends(get_cv_optimizer)],
) -> OptimizationResult:
    return await optimizer.optimize(
        match_id=body.match_id,
        job_id=body.job_id,
        cv_id=body.cv_id,
        original_tex=body.original_tex,
        job_description=body.job_description,
        job_skills=body.job_skills,
        missing_skills=body.missing_skills,
        recommendations=body.recommendations,
    )

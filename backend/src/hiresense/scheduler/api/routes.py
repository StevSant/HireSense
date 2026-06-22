from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hiresense.identity.api.dependencies import require_admin, require_auth
from hiresense.scheduler.api.dependencies import get_scheduler_provider
from hiresense.scheduler.api.provider import SchedulerProvider
from hiresense.scheduler.domain import JobRun, ScheduledJobView

router = APIRouter(prefix="/scheduler", tags=["scheduler"], dependencies=[Depends(require_auth)])


class ToggleRequest(BaseModel):
    enabled: bool


def _require_known(provider: SchedulerProvider, name: str) -> None:
    if not provider.has_job(name):
        raise HTTPException(status_code=404, detail=f"Unknown job: {name}")


@router.get("/jobs", response_model=list[ScheduledJobView])
def list_jobs(
    provider: Annotated[SchedulerProvider, Depends(get_scheduler_provider)],
) -> list[ScheduledJobView]:
    return provider.list_jobs()


@router.get("/jobs/{name}/runs", response_model=list[JobRun])
def job_runs(
    name: str,
    provider: Annotated[SchedulerProvider, Depends(get_scheduler_provider)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[JobRun]:
    _require_known(provider, name)
    return provider.runs(name, limit)


@router.post("/jobs/{name}/toggle", response_model=ScheduledJobView)
def toggle_job(
    name: str,
    body: ToggleRequest,
    provider: Annotated[SchedulerProvider, Depends(get_scheduler_provider)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> ScheduledJobView:
    _require_known(provider, name)
    return provider.set_enabled(name, body.enabled)


@router.post("/jobs/{name}/run-now", response_model=JobRun)
async def run_now(
    name: str,
    provider: Annotated[SchedulerProvider, Depends(get_scheduler_provider)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> JobRun:
    _require_known(provider, name)
    return await provider.run_now(name)

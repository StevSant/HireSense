from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.services import IngestionOrchestrator

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def get_ingestion_orchestrator() -> IngestionOrchestrator:
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")


class FetchResponse(BaseModel):
    count: int
    jobs: list[NormalizedJob]


@router.post("/fetch", response_model=FetchResponse)
async def fetch_jobs(
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
) -> FetchResponse:
    jobs = await orchestrator.run()
    return FetchResponse(count=len(jobs), jobs=jobs)

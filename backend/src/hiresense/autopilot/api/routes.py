from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from hiresense.autopilot.api.dependencies import get_autopilot_provider
from hiresense.autopilot.api.provider import AutopilotProvider
from hiresense.autopilot.domain import AutopilotDraft, PipelineResult
from hiresense.identity.api.dependencies import require_admin, require_auth

router = APIRouter(prefix="/autopilot", tags=["autopilot"], dependencies=[Depends(require_auth)])


@router.get("/drafts", response_model=list[AutopilotDraft])
def list_drafts(
    provider: Annotated[AutopilotProvider, Depends(get_autopilot_provider)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AutopilotDraft]:
    return provider.get_repo().list(limit)


@router.post("/run", response_model=PipelineResult)
async def run_now(
    provider: Annotated[AutopilotProvider, Depends(get_autopilot_provider)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> PipelineResult:
    return await provider.get_service().run()

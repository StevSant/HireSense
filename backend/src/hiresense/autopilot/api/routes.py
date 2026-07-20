from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from hiresense.autopilot.api.dependencies import get_autopilot_provider
from hiresense.autopilot.api.provider import AutopilotProvider
from hiresense.autopilot.domain import AutopilotDraft, AutopilotPipelineService
from hiresense.identity.api.dependencies import require_admin, require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autopilot", tags=["autopilot"], dependencies=[Depends(require_auth)])

# Holds references to fire-and-forget run-now tasks so they aren't garbage
# collected mid-execution (a well-known asyncio.create_task gotcha).
_background_tasks: set[asyncio.Task[Any]] = set()


async def _run_and_log_failures(service: AutopilotPipelineService) -> None:
    """Background wrapper for the manual run-now trigger. `run_claimed()`
    isolates per-entry drafting failures internally, so this only guards
    against something unexpected escaping — without it, a failure here would
    surface only as an unhandled "Task exception was never retrieved"
    warning with no context (mirrors JobRunner's scheduled-job handling)."""
    try:
        await service.run_claimed()
    except Exception:  # noqa: BLE001 - fire-and-forget task must not fail silently
        logger.exception("Autopilot manual run failed")


@router.get("/drafts", response_model=list[AutopilotDraft])
def list_drafts(
    provider: Annotated[AutopilotProvider, Depends(get_autopilot_provider)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AutopilotDraft]:
    return provider.get_repo().list(limit)


@router.post("/run", status_code=202)
async def run_now(
    provider: Annotated[AutopilotProvider, Depends(get_autopilot_provider)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> JSONResponse:
    """Fires the autopilot pipeline in the background and returns immediately.

    Rejects with 409 if a run (scheduled or manual) is already in flight —
    `AutopilotPipelineService` holds the single guard both triggers share.
    """
    service = provider.get_service()
    if not service.try_start():
        return JSONResponse({"status": "already_running"}, status_code=409)
    task = asyncio.create_task(_run_and_log_failures(service))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return JSONResponse({"status": "started"}, status_code=202)

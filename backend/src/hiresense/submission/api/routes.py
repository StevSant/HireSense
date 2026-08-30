from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from hiresense.identity.api.dependencies import require_admin, require_auth
from hiresense.submission.api.dependencies import get_submission_provider
from hiresense.submission.api.provider import SubmissionProvider
from hiresense.submission.api.schemas import (
    CompleteRequest,
    EnqueueRequest,
    LeaseRequest,
    ObserveRequest,
    ResumeRequest,
)
from hiresense.submission.domain import (
    AgentContext,
    SubmissionAttempt,
    SubmissionEvent,
    SubmissionStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/submission", tags=["submission"], dependencies=[Depends(require_auth)])


@router.post("/lease", response_model=list[SubmissionAttempt])
def lease(
    body: LeaseRequest,
    provider: Annotated[SubmissionProvider, Depends(get_submission_provider)],
) -> list[SubmissionAttempt]:
    """Claim queued attempts for one runner. Expired leases are swept first so
    a crashed runner's work is picked up rather than stranded."""
    service = provider.get_service()
    service.sweep_expired()
    return service.lease(body.runner_id, body.capacity)


@router.get("/attempts", response_model=list[SubmissionAttempt])
def list_attempts(
    provider: Annotated[SubmissionProvider, Depends(get_submission_provider)],
    status: SubmissionStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SubmissionAttempt]:
    return provider.get_repo().list(status=status, limit=limit)


@router.get("/attempts/{attempt_id}", response_model=SubmissionAttempt)
def get_attempt(
    attempt_id: uuid.UUID,
    provider: Annotated[SubmissionProvider, Depends(get_submission_provider)],
) -> SubmissionAttempt:
    attempt = provider.get_repo().get(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Submission attempt not found")
    return attempt


@router.get("/attempts/{attempt_id}/events", response_model=list[SubmissionEvent])
def list_events(
    attempt_id: uuid.UUID,
    provider: Annotated[SubmissionProvider, Depends(get_submission_provider)],
) -> list[SubmissionEvent]:
    """The audit tape: every field the agent filled and why."""
    if provider.get_repo().get(attempt_id) is None:
        raise HTTPException(status_code=404, detail="Submission attempt not found")
    return provider.get_repo().events(attempt_id)


@router.post("/attempts/{attempt_id}/observe")
async def observe(
    attempt_id: uuid.UUID,
    body: ObserveRequest,
    provider: Annotated[SubmissionProvider, Depends(get_submission_provider)],
) -> Any:
    """Runner posts what it sees; the server decides the next action.

    The decision lives here, not in the runner, so the LLM key, the candidate's
    profile, and the grounding rule never leave the backend.
    """
    repo = provider.get_repo()
    attempt = repo.get(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Submission attempt not found")

    builder = provider.get_context_builder()
    context = await builder.build(attempt) if builder is not None else AgentContext()
    action = await provider.get_service().observe(attempt_id, body.observation, context)
    return action.model_dump(mode="json")


@router.post("/attempts/{attempt_id}/heartbeat", response_model=SubmissionAttempt)
def heartbeat(
    attempt_id: uuid.UUID,
    provider: Annotated[SubmissionProvider, Depends(get_submission_provider)],
) -> SubmissionAttempt:
    attempt = provider.get_service().heartbeat(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Submission attempt not found")
    return attempt


@router.post("/attempts/{attempt_id}/complete", response_model=SubmissionAttempt)
def complete(
    attempt_id: uuid.UUID,
    body: CompleteRequest,
    provider: Annotated[SubmissionProvider, Depends(get_submission_provider)],
) -> SubmissionAttempt:
    try:
        return provider.get_service().complete(
            attempt_id, status=body.status, evidence=body.evidence
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/attempts/{attempt_id}/resume", response_model=SubmissionAttempt)
async def resume(
    attempt_id: uuid.UUID,
    body: ResumeRequest,
    provider: Annotated[SubmissionProvider, Depends(get_submission_provider)],
) -> SubmissionAttempt:
    """Supply the answers the agent could not ground, and re-queue the attempt."""
    try:
        return await provider.get_service().resume(attempt_id, body.answers)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/attempts/{attempt_id}/abandon", response_model=SubmissionAttempt)
def abandon(
    attempt_id: uuid.UUID,
    provider: Annotated[SubmissionProvider, Depends(get_submission_provider)],
) -> SubmissionAttempt:
    try:
        return provider.get_service().abandon(attempt_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/enqueue", response_model=SubmissionAttempt, status_code=201)
def enqueue(
    body: EnqueueRequest,
    provider: Annotated[SubmissionProvider, Depends(get_submission_provider)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> SubmissionAttempt:
    """Manually queue one application. Rejects with 409 when the daily cap is
    spent or the application already has a live attempt."""
    attempt = provider.get_service().enqueue(
        application_id=body.application_id,
        job_id=body.job_id,
        packet_id=body.packet_id,
        channel=body.channel,
        target_url=body.target_url,
    )
    if attempt is None:
        raise HTTPException(
            status_code=409,
            detail="Daily submission cap reached, or this application already has a live attempt",
        )
    return attempt

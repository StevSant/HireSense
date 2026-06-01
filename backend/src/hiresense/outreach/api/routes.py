from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from hiresense.identity.api.dependencies import require_auth
from hiresense.outreach.api.dependencies import get_outreach_service
from hiresense.outreach.api.schemas import (
    GenerateRequest,
    GenerateResponse,
    RecordRequest,
)
from hiresense.outreach.domain import OutreachEvent, OutreachNudge, OutreachService
from hiresense.outreach.domain.message_generator import OutreachUnavailableError

router = APIRouter(prefix="/outreach", tags=["outreach"], dependencies=[Depends(require_auth)])


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: GenerateRequest, service: OutreachService = Depends(get_outreach_service)
) -> GenerateResponse:
    try:
        message = await service.generate(
            body.application_id, contact_name=body.contact_name, channel=body.channel
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OutreachUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Outreach generation unavailable") from exc
    return GenerateResponse(message=message)


@router.post("/record", response_model=OutreachEvent, status_code=201)
def record(
    body: RecordRequest, service: OutreachService = Depends(get_outreach_service)
) -> OutreachEvent:
    try:
        return service.record(
            body.application_id, kind=body.kind, message=body.message,
            contact_name=body.contact_name, channel=body.channel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/events", response_model=list[OutreachEvent])
def list_events(
    application_id: uuid.UUID, service: OutreachService = Depends(get_outreach_service)
) -> list[OutreachEvent]:
    return service.list_for(application_id)


@router.post("/nudge", response_model=list[OutreachNudge])
def nudge(service: OutreachService = Depends(get_outreach_service)) -> list[OutreachNudge]:
    return service.due_followups()

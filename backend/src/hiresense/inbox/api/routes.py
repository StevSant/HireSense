from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from hiresense.identity.api.dependencies import require_auth
from hiresense.inbox.api.dependencies import get_inbox_provider
from hiresense.inbox.api.provider import InboxProvider
from hiresense.inbox.domain import DetectedSignal, InboundEmail, SignalState
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.domain import TrackingService
from hiresense.tracking.domain.models import ApplicationStatus

router = APIRouter(tags=["inbox"], dependencies=[Depends(require_auth)])


class IngestEmailRequest(BaseModel):
    from_address: str
    subject: str
    body: str
    message_id: str | None = None
    received_at: datetime | None = None


@router.post("/tracking/ingest-email", response_model=None, status_code=201)
async def ingest_email(
    body: IngestEmailRequest,
    provider: Annotated[InboxProvider, Depends(get_inbox_provider)],
) -> DetectedSignal | Response:
    email = InboundEmail(
        message_id=body.message_id or f"manual-{uuid_mod.uuid4()}",
        from_address=body.from_address,
        subject=body.subject,
        body=body.body,
        received_at=body.received_at or datetime.now(timezone.utc),
    )
    signal = await provider.get_service().ingest_one(email)
    if signal is None:
        return Response(status_code=204)
    return signal


@router.get("/inbox/signals", response_model=list[DetectedSignal])
def list_signals(
    provider: Annotated[InboxProvider, Depends(get_inbox_provider)],
    state: SignalState | None = None,
) -> list[DetectedSignal]:
    return provider.get_repo().list(state=state)


@router.post("/inbox/signals/{signal_id}/confirm", response_model=DetectedSignal)
async def confirm_signal(
    signal_id: uuid_mod.UUID,
    provider: Annotated[InboxProvider, Depends(get_inbox_provider)],
    tracking: Annotated[TrackingService, Depends(get_tracking_service)],
) -> DetectedSignal:
    repo = provider.get_repo()
    signal = repo.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.matched_application_id is None or signal.proposed_status is None:
        raise HTTPException(status_code=409, detail="Signal has no matched application to update")
    await tracking.update_status(
        signal.matched_application_id, ApplicationStatus(signal.proposed_status)
    )
    updated = repo.set_state(signal_id, SignalState.APPLIED)
    if updated is None:  # signal vanished between get and set_state
        raise HTTPException(status_code=404, detail="Signal not found")
    return updated


@router.post("/inbox/signals/{signal_id}/dismiss", response_model=DetectedSignal)
def dismiss_signal(
    signal_id: uuid_mod.UUID,
    provider: Annotated[InboxProvider, Depends(get_inbox_provider)],
) -> DetectedSignal:
    repo = provider.get_repo()
    if repo.get(signal_id) is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return repo.set_state(signal_id, SignalState.DISMISSED)

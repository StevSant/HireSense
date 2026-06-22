from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from hiresense.identity.api.dependencies import require_admin, require_auth
from hiresense.notifications.api.dependencies import get_notification_service
from hiresense.notifications.domain import NotificationService
from hiresense.ports import EmailUnavailableError

router = APIRouter(
    prefix="/notifications", tags=["notifications"], dependencies=[Depends(require_auth)]
)


class NotificationStatus(BaseModel):
    enabled: bool
    recipient_masked: str | None


@router.get("/status", response_model=NotificationStatus)
def status(
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationStatus:
    return NotificationStatus(
        enabled=service.enabled, recipient_masked=service.masked_recipient()
    )


@router.post("/test", status_code=200)
async def send_test(
    service: Annotated[NotificationService, Depends(get_notification_service)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> dict[str, bool]:
    try:
        await service.send_test()
    except EmailUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"sent": True}

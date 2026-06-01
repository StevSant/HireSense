from __future__ import annotations

import uuid

from pydantic import BaseModel

from hiresense.outreach.domain import OutreachEvent, OutreachEventKind, OutreachNudge


class GenerateRequest(BaseModel):
    application_id: uuid.UUID
    contact_name: str | None = None
    channel: str | None = None


class GenerateResponse(BaseModel):
    message: str


class RecordRequest(BaseModel):
    application_id: uuid.UUID
    kind: OutreachEventKind
    message: str | None = None
    contact_name: str | None = None
    channel: str | None = None


__all__ = [
    "GenerateRequest",
    "GenerateResponse",
    "OutreachEvent",
    "OutreachNudge",
    "RecordRequest",
]

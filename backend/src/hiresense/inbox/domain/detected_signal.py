from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel

from hiresense.inbox.domain.email_signal_kind import EmailSignalKind
from hiresense.inbox.domain.signal_state import SignalState


class DetectedSignal(BaseModel):
    """A detected, reviewable email signal (pure domain model)."""

    id: uuid_mod.UUID | None = None
    message_id: str
    from_address: str
    subject: str
    received_at: datetime
    kind: EmailSignalKind
    company: str | None = None
    role: str | None = None
    confidence: float = 0.0
    matched_application_id: uuid_mod.UUID | None = None
    proposed_status: str | None = None
    state: SignalState = SignalState.PENDING
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

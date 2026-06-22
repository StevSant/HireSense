from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class InboundEmail(BaseModel):
    """A raw inbound email to classify (pure domain model)."""

    message_id: str
    from_address: str
    subject: str
    body: str
    received_at: datetime

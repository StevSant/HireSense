from __future__ import annotations

from pydantic import BaseModel


class EmailMessage(BaseModel):
    """A plain-text email to send via an EmailSenderPort."""

    to: str
    subject: str
    body: str

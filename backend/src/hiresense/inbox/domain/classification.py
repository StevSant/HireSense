from __future__ import annotations

from pydantic import BaseModel

from hiresense.inbox.domain.email_signal_kind import EmailSignalKind


class EmailClassification(BaseModel):
    """Result of classifying one email."""

    job_related: bool
    kind: EmailSignalKind = EmailSignalKind.OTHER
    company: str | None = None
    role: str | None = None
    confidence: float = 0.0

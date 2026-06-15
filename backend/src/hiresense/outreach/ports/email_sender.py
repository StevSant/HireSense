from __future__ import annotations

from typing import Protocol

from hiresense.outreach.domain.email_message import EmailMessage


class EmailSenderPort(Protocol):
    """Sends an outreach email. Implementations raise EmailUnavailableError when
    sending isn't possible (e.g. SMTP not configured)."""

    def send(self, message: EmailMessage) -> None: ...

from __future__ import annotations

from typing import Protocol

from hiresense.kernel import EmailMessage


class EmailSenderPort(Protocol):
    """Sends an email. Implementations raise EmailUnavailableError when sending
    isn't possible (e.g. SMTP not configured)."""

    def send(self, message: EmailMessage) -> None: ...

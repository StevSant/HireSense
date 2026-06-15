from __future__ import annotations

import smtplib
from email.message import EmailMessage as MimeEmailMessage

from hiresense.outreach.domain.email_message import EmailMessage
from hiresense.outreach.domain.email_unavailable_error import EmailUnavailableError


class SmtpEmailSender:
    """Sends outreach email over SMTP. Config-gated: when host/from are unset it
    raises EmailUnavailableError instead of pretending to send, so dev runs
    without SMTP and the API surfaces a clear 503."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        use_tls: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._use_tls = use_tls

    def send(self, message: EmailMessage) -> None:
        if not self._host or not self._from_email:
            raise EmailUnavailableError("SMTP is not configured")
        mime = MimeEmailMessage()
        mime["From"] = self._from_email
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(mime)

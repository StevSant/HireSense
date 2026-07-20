from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage as MimeEmailMessage

from hiresense.kernel import EmailMessage
from hiresense.ports import EmailUnavailableError


class SmtpEmailSender:
    """Sends email over SMTP. Config-gated: when host/from are unset it raises
    EmailUnavailableError instead of pretending to send.

    Secure by default: refuses to log in over a non-TLS channel (which would send
    credentials in plaintext) and verifies the server certificate on STARTTLS.
    Pass allow_insecure=True only for a trusted local/dev server."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        use_tls: bool,
        timeout: float,
        allow_insecure: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._use_tls = use_tls
        self._timeout = timeout
        self._allow_insecure = allow_insecure

    def send(self, message: EmailMessage) -> None:
        if not self._host or not self._from_email:
            raise EmailUnavailableError("SMTP is not configured")
        if self._username and not self._use_tls and not self._allow_insecure:
            raise EmailUnavailableError(
                "Refusing SMTP login over a non-TLS connection: credentials would be "
                "sent in plaintext. Enable SMTP_USE_TLS, or set SMTP_ALLOW_INSECURE=true "
                "for a trusted local/dev server."
            )
        self._reject_header_injection("to", message.to)
        self._reject_header_injection("subject", message.subject)
        mime = MimeEmailMessage()
        mime["From"] = self._from_email
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            if self._use_tls:
                smtp.starttls(context=self._ssl_context())
            if self._username:
                smtp.login(self._username, self._password)
            # Set the envelope recipient explicitly instead of letting smtplib derive
            # it from the (untrusted) To header.
            smtp.send_message(mime, to_addrs=[message.to])

    @staticmethod
    def _reject_header_injection(field: str, value: str) -> None:
        """Defense-in-depth against CRLF header injection (CWE-93). EmailMessage
        with policy=default already refolds/validates headers, but the outreach
        relay feeds these from caller-controlled values, so guard explicitly."""
        if "\r" in value or "\n" in value:
            raise ValueError(f"Email {field} must not contain CR or LF characters")

    def _ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context()
        if self._allow_insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context

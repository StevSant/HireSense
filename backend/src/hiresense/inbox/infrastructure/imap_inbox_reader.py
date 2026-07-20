from __future__ import annotations

import email as email_lib
import imaplib
import logging
import ssl
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from hiresense.inbox.domain import InboundEmail

logger = logging.getLogger(__name__)


class ImapInboxReader:
    """Reads UNSEEN emails over IMAP. Config-gated: a blank host disables it
    (returns []). Never raises — connection/parse errors log and return what was
    gathered so a scan degrades to a no-op."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        folder: str,
        use_ssl: bool,
        timeout: float,
        allow_insecure: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._folder = folder
        self._use_ssl = use_ssl
        self._timeout = timeout
        self._allow_insecure = allow_insecure

    def fetch_unseen(self) -> list[InboundEmail]:
        if not self._host:
            return []
        try:
            return self._fetch()
        except Exception:  # noqa: BLE001 - inbox read is best-effort
            logger.exception("inbox: IMAP fetch failed")
            return []

    def _fetch(self) -> list[InboundEmail]:
        if not self._use_ssl and self._username and not self._allow_insecure:
            logger.warning(
                "inbox: refusing IMAP login over a non-SSL connection (credentials "
                "would be sent in plaintext); enable IMAP_USE_SSL, or set "
                "IMAP_ALLOW_INSECURE=true for a trusted local/dev server"
            )
            return []
        client = (
            imaplib.IMAP4_SSL(
                self._host, self._port, ssl_context=self._ssl_context(), timeout=self._timeout
            )
            if self._use_ssl
            else imaplib.IMAP4(self._host, self._port, timeout=self._timeout)
        )
        out: list[InboundEmail] = []
        try:
            client.login(self._username, self._password)
            client.select(self._folder)
            _, data = client.search(None, "UNSEEN")
            ids = data[0].split() if data and data[0] else []
            for num in ids:
                _, msg_data = client.fetch(num, "(RFC822)")
                if not msg_data or not isinstance(msg_data[0], tuple):
                    continue
                parsed = self._parse(msg_data[0][1])
                if parsed is not None:
                    out.append(parsed)
        finally:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass
        return out

    def _ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context()
        if self._allow_insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context

    @staticmethod
    def _parse(raw: bytes) -> InboundEmail | None:
        try:
            msg = email_lib.message_from_bytes(raw)
            body = ImapInboxReader._extract_body(msg)
            received = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
            return InboundEmail(
                message_id=msg.get("Message-ID") or "",
                from_address=msg.get("From") or "",
                subject=msg.get("Subject") or "",
                body=body,
                received_at=received or datetime.now(timezone.utc),
            )
        except Exception:  # noqa: BLE001
            logger.warning("inbox: could not parse an email")
            return None

    @staticmethod
    def _extract_body(msg) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(part.get_content_charset() or "utf-8", "replace")
            return ""
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(msg.get_content_charset() or "utf-8", "replace")
        return ""

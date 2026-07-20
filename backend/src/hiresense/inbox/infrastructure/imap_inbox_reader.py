from __future__ import annotations

import email as email_lib
import imaplib
import logging
import ssl
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from hiresense.inbox.domain import InboundEmail, synthesize_message_id
from hiresense.observability import get_domain_metrics

logger = logging.getLogger(__name__)

# Connection-level IMAP failures that are safe to retry (server dropped the
# connection, socket timeout/reset). imaplib.IMAP4.error (protocol/auth) is a
# permanent failure and deliberately excluded.
_RETRYABLE_IMAP_ERRORS = (imaplib.IMAP4.abort, OSError)


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
        max_retries: int = 0,
        retry_base_delay: float = 1.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._folder = folder
        self._use_ssl = use_ssl
        self._timeout = timeout
        self._allow_insecure = allow_insecure
        # Bounded retry for transient connection errors (issue #163). 0 disables
        # retrying; a fetch that still fails is counted and degrades to [].
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay

    def fetch_unseen(self) -> list[InboundEmail]:
        if not self._host:
            return []
        for attempt in range(self._max_retries + 1):
            try:
                return self._fetch()
            except _RETRYABLE_IMAP_ERRORS as exc:
                if attempt < self._max_retries:
                    delay = self._retry_base_delay * (2**attempt)
                    logger.warning(
                        "inbox: IMAP fetch failed (attempt %d/%d), retrying in %.2fs: %s",
                        attempt + 1,
                        self._max_retries,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                    continue
                logger.exception("inbox: IMAP fetch failed after %d retries", self._max_retries)
                self._record_failure()
                return []
            except Exception:  # noqa: BLE001 - non-transient (auth/protocol); don't retry
                logger.exception("inbox: IMAP fetch failed")
                self._record_failure()
                return []
        return []  # pragma: no cover - the loop always returns before exhausting

    @staticmethod
    def _record_failure() -> None:
        get_domain_metrics().automation_failures_total.add(1, {"component": "inbox_fetch"})

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
            from_address = msg.get("From") or ""
            subject = msg.get("Subject") or ""
            received_at = received or datetime.now(timezone.utc)
            # A missing Message-ID must not collapse every header-less email onto
            # the same empty dedup key — synthesize a stable one from the content.
            message_id = msg.get("Message-ID") or synthesize_message_id(
                from_address=from_address,
                subject=subject,
                received_at=received_at,
                body=body,
            )
            return InboundEmail(
                message_id=message_id,
                from_address=from_address,
                subject=subject,
                body=body,
                received_at=received_at,
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

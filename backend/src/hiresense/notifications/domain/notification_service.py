from __future__ import annotations

import asyncio
import logging
from typing import Any

from hiresense.kernel import EmailMessage
from hiresense.notifications.domain.digest_email import render_digest_email
from hiresense.notifications.domain.inbox_signals_email import render_inbox_signals_email
from hiresense.notifications.domain.pipeline_drafts_email import render_pipeline_drafts_email
from hiresense.notifications.domain.job_failure_email import render_job_failure_email
from hiresense.ports import EmailUnavailableError

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends digest + failure-alert email. Disabled (blank recipient) -> no-op.

    Best-effort: send errors on the notify_* paths are logged and swallowed so a
    notification failure never breaks a scheduled job. send_test() lets errors
    propagate so the admin endpoint can surface them as 503.
    """

    def __init__(self, *, sender: Any, to_email: str) -> None:
        self._sender = sender
        self._to = to_email

    @property
    def enabled(self) -> bool:
        return bool(self._to)

    def masked_recipient(self) -> str | None:
        """Masked recipient for the status API (never exposes the raw address)."""
        if not self._to:
            return None
        name, _, domain = self._to.partition("@")
        head = name[0] if name else ""
        return f"{head}***@{domain}" if domain else f"{head}***"

    async def notify_new_matches(self, digest: Any) -> bool:
        subject, body = render_digest_email(digest)
        return await self._safe_send(subject, body)

    async def notify_job_failure(self, job_name: str, detail: str | None) -> bool:
        subject, body = render_job_failure_email(job_name, detail)
        return await self._safe_send(subject, body)

    async def notify_inbox_signals(self, count: int) -> bool:
        subject, body = render_inbox_signals_email(count)
        return await self._safe_send(subject, body)

    async def notify_pipeline_drafts(self, count: int) -> bool:
        subject, body = render_pipeline_drafts_email(count)
        return await self._safe_send(subject, body)

    async def send_test(self) -> None:
        if not self.enabled:
            raise EmailUnavailableError("Notifications are not configured (blank recipient)")
        await self._send("HireSense: test notification", "This is a HireSense test notification.")

    async def _safe_send(self, subject: str, body: str) -> bool:
        if not self.enabled:
            return False
        try:
            await self._send(subject, body)
            return True
        except Exception:  # noqa: BLE001 - notifications are best-effort
            logger.exception("Notification send failed")
            return False

    async def _send(self, subject: str, body: str) -> None:
        await asyncio.to_thread(
            self._sender.send, EmailMessage(to=self._to, subject=subject, body=body)
        )

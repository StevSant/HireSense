from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from hiresense.inbox.domain.application_matcher import ApplicationMatcher
from hiresense.inbox.domain.detected_signal import DetectedSignal
from hiresense.inbox.domain.email_classifier import EmailClassifier
from hiresense.inbox.domain.inbound_email import InboundEmail
from hiresense.inbox.domain.ports import DetectedSignalRepository, InboxReaderPort

logger = logging.getLogger(__name__)


class InboxProcessingService:
    """Orchestrates one inbox scan: read → classify → match → store pending
    signals (dedup by message_id). Best-effort: never raises into the caller."""

    def __init__(
        self,
        *,
        reader: InboxReaderPort,
        repo: DetectedSignalRepository,
        classifier: EmailClassifier,
        matcher: ApplicationMatcher,
        list_active: Callable[[], list[Any]],
        notifier: Any | None = None,
    ) -> None:
        self._reader = reader
        self._repo = repo
        self._classifier = classifier
        self._matcher = matcher
        self._list_active = list_active
        self._notifier = notifier

    async def run(self) -> int:
        emails = await asyncio.to_thread(self._reader.fetch_unseen)
        new_count = 0
        for email in emails:
            signal = await self._process(email)
            if signal is not None:
                new_count += 1
        if new_count and self._notifier is not None:
            try:
                await self._notifier.notify_inbox_signals(new_count)
            except Exception:  # noqa: BLE001 - notification is best-effort
                logger.exception("inbox: signal notification failed")
        return new_count

    async def ingest_one(self, email: InboundEmail) -> DetectedSignal | None:
        return await self._process(email)

    async def _process(self, email: InboundEmail) -> DetectedSignal | None:
        if self._repo.exists_message_id(email.message_id):
            return None
        classification = await self._classifier.classify(email)
        if not classification.job_related:
            return None
        matched_id, proposed = self._matcher.match(classification, self._list_active())
        signal = DetectedSignal(
            message_id=email.message_id,
            from_address=email.from_address,
            subject=email.subject,
            received_at=email.received_at,
            kind=classification.kind,
            company=classification.company,
            role=classification.role,
            confidence=classification.confidence,
            matched_application_id=matched_id,
            proposed_status=proposed,
        )
        return self._repo.add(signal)

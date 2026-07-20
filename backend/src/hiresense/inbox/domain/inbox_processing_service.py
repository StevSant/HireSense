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

# Bounds concurrent classify+match+store work per inbox scan (each email chains
# an LLM classification call). Module-level constant — a config knob isn't
# warranted here, unlike autopilot's LLM-heavier per-draft concurrency.
_PROCESSING_CONCURRENCY = 3


class InboxProcessingService:
    """Orchestrates one inbox scan: read → classify → match → store pending
    signals (dedup by message_id). `run()` is best-effort per email: a failing
    classification is isolated and logged, never aborting the rest of the
    batch. `ingest_one()` (the /tracking/ingest-email webhook) does NOT
    isolate failures — it must propagate them so the route returns 500 and
    the provider redelivers, rather than silently dropping a message the
    webhook already reported as 204/"handled"."""

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
        try:
            emails = await asyncio.to_thread(self._reader.fetch_unseen)
        except Exception:  # noqa: BLE001 - inbox read is best-effort; a scan must never raise
            logger.exception("inbox: fetch_unseen failed")
            return 0

        # Dedup BEFORE the concurrent gather: two bounded tasks racing on the
        # same message_id could both pass an exists check before either had
        # inserted. All emails come from one fetch, so filtering the batch by
        # already-stored ids + an in-batch id set up front is enough — no two
        # tasks below ever end up processing the same message_id.
        to_process: list[InboundEmail] = []
        seen_in_batch: set[str] = set()
        for email in emails:
            if email.message_id in seen_in_batch:
                continue
            seen_in_batch.add(email.message_id)
            if await asyncio.to_thread(self._repo.exists_message_id, email.message_id):
                continue
            to_process.append(email)

        semaphore = asyncio.Semaphore(_PROCESSING_CONCURRENCY)

        async def _bounded(email: InboundEmail) -> DetectedSignal | None:
            async with semaphore:
                try:
                    return await self._process(email)
                except Exception:  # noqa: BLE001 - one bad email must not abort the scan
                    logger.exception("inbox: processing email %r failed", email.message_id)
                    return None

        results = await asyncio.gather(*(_bounded(email) for email in to_process))
        new_count = sum(1 for r in results if r is not None)

        if new_count and self._notifier is not None:
            try:
                await self._notifier.notify_inbox_signals(new_count)
            except Exception:  # noqa: BLE001 - notification is best-effort
                logger.exception("inbox: signal notification failed")
        return new_count

    async def ingest_one(self, email: InboundEmail) -> DetectedSignal | None:
        return await self._process(email)

    async def _process(self, email: InboundEmail) -> DetectedSignal | None:
        """Raises on classifier/matcher/repo failure — callers decide how to
        handle that: `run()`'s `_bounded` wrapper isolates it per email;
        `ingest_one()` (the webhook) lets it propagate so the caller retries."""
        if await asyncio.to_thread(self._repo.exists_message_id, email.message_id):
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
        return await asyncio.to_thread(self._repo.add, signal)

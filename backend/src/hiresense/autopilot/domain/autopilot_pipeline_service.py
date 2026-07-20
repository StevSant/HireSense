from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from hiresense.autopilot.domain.autopilot_draft import AutopilotDraft
from hiresense.autopilot.domain.draft_status import DraftStatus
from hiresense.autopilot.domain.pipeline_result import PipelineResult
from hiresense.autopilot.domain.ports import ApplicationDrafter, DraftRepository

logger = logging.getLogger(__name__)


class AutopilotPipelineService:
    """Reads the latest autohunt digest and drafts applications for its top-N new
    matches. Best-effort: per-job failures are recorded and skipped; run() never
    raises into the caller."""

    def __init__(
        self,
        *,
        latest_digest: Callable[[], Any],
        drafter: ApplicationDrafter,
        repo: DraftRepository,
        top_n: int,
        concurrency: int = 3,
        notifier: Any | None = None,
    ) -> None:
        self._latest_digest = latest_digest
        self._drafter = drafter
        self._repo = repo
        self._top_n = top_n
        self._concurrency = concurrency
        self._notifier = notifier
        # Guards against a scheduled run and a manual run-now overlapping —
        # both paths end up calling into this same service instance.
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def try_start(self) -> bool:
        """Synchronously claim the in-flight slot. Returns False if a run is
        already active. Has no `await` inside, so the check-and-set is atomic
        under cooperative scheduling — callers (the run-now route) can use it
        to reject a concurrent request before scheduling any work."""
        if self._running:
            return False
        self._running = True
        return True

    def _finish(self) -> None:
        self._running = False

    async def run(self) -> PipelineResult:
        """Guarded entry point used by the scheduler. Best-effort: never raises
        into the caller. If a run is already in flight — scheduled or started
        manually via the run-now endpoint — this is a no-op so the two can
        never overlap."""
        if not self.try_start():
            logger.info("autopilot: run() skipped, a run is already in flight")
            return PipelineResult()
        return await self.run_claimed()

    async def run_claimed(self) -> PipelineResult:
        """Execute the pipeline for a caller that already claimed the in-flight
        slot via `try_start()` (the run-now route's background task). Always
        releases the slot when done, success or failure."""
        try:
            return await self._execute()
        finally:
            self._finish()

    async def _execute(self) -> PipelineResult:
        digest = self._latest_digest()
        entries = list(getattr(digest, "entries", []) or [])[: self._top_n]

        # Dedup BEFORE the concurrent gather: entries are distinct jobs, so a
        # sequential existence check up front keeps dedup correct without
        # needing a lock inside the bounded draft path below.
        to_draft: list[Any] = []
        skipped = 0
        for entry in entries:
            if await asyncio.to_thread(self._repo.exists_for_job, entry.job_id):
                skipped += 1
                continue
            to_draft.append(entry)

        semaphore = asyncio.Semaphore(self._concurrency)

        async def _bounded_draft(entry: Any) -> AutopilotDraft:
            async with semaphore:
                return await self._draft_one(entry)

        drafts = list(await asyncio.gather(*(_bounded_draft(entry) for entry in to_draft)))
        created = sum(1 for d in drafts if d.status is not DraftStatus.FAILED)

        if created and self._notifier is not None:
            try:
                await self._notifier.notify_pipeline_drafts(created)
            except Exception:  # noqa: BLE001 - notification is best-effort
                logger.exception("autopilot: draft notification failed")
        return PipelineResult(created=created, skipped=skipped, drafts=drafts)

    async def _draft_one(self, entry: Any) -> AutopilotDraft:
        job_id = entry.job_id
        try:
            application_id, status, detail = await self._drafter.draft(job_id)
        except Exception as exc:  # noqa: BLE001 - one bad job must not abort the batch
            logger.exception("autopilot: drafting job %r failed", job_id)
            application_id, status, detail = None, DraftStatus.FAILED, str(exc)
        draft = AutopilotDraft(
            job_id=job_id,
            application_id=application_id,
            job_title=getattr(entry, "title", None),
            company=getattr(entry, "company", None),
            status=status,
            detail=detail,
        )
        return await asyncio.to_thread(self._repo.add, draft)

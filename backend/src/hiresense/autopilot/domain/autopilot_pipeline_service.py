from __future__ import annotations

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
        notifier: Any | None = None,
    ) -> None:
        self._latest_digest = latest_digest
        self._drafter = drafter
        self._repo = repo
        self._top_n = top_n
        self._notifier = notifier

    async def run(self) -> PipelineResult:
        digest = self._latest_digest()
        entries = list(getattr(digest, "entries", []) or [])[: self._top_n]
        created = 0
        skipped = 0
        drafts: list[AutopilotDraft] = []
        for entry in entries:
            job_id = entry.job_id
            if self._repo.exists_for_job(job_id):
                skipped += 1
                continue
            draft = await self._draft_one(entry)
            drafts.append(draft)
            if draft.status is not DraftStatus.FAILED:
                created += 1
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
        return self._repo.add(draft)

from __future__ import annotations

import asyncio
import logging
from typing import Any

from hiresense.autopilot.domain.autopilot_draft import AutopilotDraft
from hiresense.autopilot.domain.draft_status import DraftStatus

logger = logging.getLogger(__name__)


class PacketApprovingEnqueuer:
    """Machine-approves a draft's application packet, then queues it to submit.

    This is the seam where a human used to stand. The existing
    `ApplicationPacket` gate is kept intact -- `ApplyService.mark_applied`
    still refuses anything that is not `approved` and `is_current()`. What
    changes is only who signs off: a packet is approved when the deterministic
    quality report passes AND the match score clears the configured floor.

    Every gate is conjunctive and every failure is a no-op, so the default
    behaviour of anything unexpected is "leave it for the human".
    """

    def __init__(
        self,
        packet_service: Any,
        submission_service: Any,
        repository: Any,
        *,
        min_score: float,
        apply_service: Any = None,
    ) -> None:
        self._packets = packet_service
        self._submissions = submission_service
        self._repo = repository
        self._min_score = min_score
        self._apply = apply_service

    async def enqueue_for_draft(self, draft: AutopilotDraft) -> None:
        try:
            await asyncio.to_thread(self._enqueue_sync, draft)
        except Exception:  # noqa: BLE001 - one bad enqueue must not abort the batch
            logger.exception("autopilot: could not enqueue draft for job %r", draft.job_id)

    def _enqueue_sync(self, draft: AutopilotDraft) -> None:
        # Only a fully drafted application is a candidate. A PARTIAL draft is
        # missing a CV, a cover letter, or a match -- exactly the material the
        # quality report grades -- so submitting it would send an incomplete
        # application under the candidate's name.
        if draft.status is not DraftStatus.DRAFTED or draft.application_id is None:
            logger.info(
                "autopilot: draft for %r is %s, not submitting",
                draft.job_id,
                draft.status.value,
            )
            return

        match = self._repo.get_latest_match(draft.application_id)
        score = float(getattr(match, "score", 0.0) or 0.0) if match is not None else 0.0
        if score < self._min_score:
            logger.info(
                "autopilot: match %.2f below submit floor %.2f for %r",
                score,
                self._min_score,
                draft.job_id,
            )
            return

        packet = self._packets.create(draft.application_id)
        if not packet.quality_report.ready:
            logger.info(
                "autopilot: packet for %r failed quality checks (%s)",
                draft.job_id,
                "; ".join(packet.quality_report.warnings),
            )
            return

        approved = self._packets.approve(packet.id)

        self._submissions.enqueue(
            application_id=draft.application_id,
            job_id=draft.job_id,
            packet_id=approved.id,
            channel=self._channel(draft),
            target_url=self._target_url(draft),
        )

    def _channel(self, draft: AutopilotDraft) -> str:
        snapshot = self._repo.get_snapshot(draft.application_id)
        return getattr(snapshot, "source", None) or "unknown"

    def _target_url(self, draft: AutopilotDraft) -> str:
        snapshot = self._repo.get_snapshot(draft.application_id)
        return getattr(snapshot, "url", None) or ""

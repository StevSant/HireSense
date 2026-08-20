from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from hiresense.ingestion.domain.job_closure_reason import JobClosureReason
from hiresense.ingestion.domain.job_history_event import JobHistoryEvent
from hiresense.ingestion.domain.job_history_event_type import JobHistoryEventType
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.ports.job_history import JobHistoryPort
from hiresense.ingestion.ports.jobs_repository import UpsertOutcome
from hiresense.shared.observability import get_domain_metrics

logger = logging.getLogger(__name__)

_RESULT_TO_EVENT: dict[UpsertResult, JobHistoryEventType] = {
    UpsertResult.INSERTED: JobHistoryEventType.INSERTED,
    UpsertResult.UPDATED: JobHistoryEventType.UPDATED,
    UpsertResult.REOPENED: JobHistoryEventType.REOPENED,
}


class JobHistoryRecorder:
    """Turns upsert outcomes and closures into persisted history.

    Every method swallows its own failures and increments
    automation_failures_total{component=job_history_record}. An audit trail
    that can fail an ingestion pass is worse than a gap in the audit trail —
    the job table, not this, is the source of truth.
    """

    def __init__(
        self,
        store: JobHistoryPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def start_run(self, trigger: str) -> str | None:
        try:
            return self._store.start_run(trigger, self._clock())
        except Exception:
            self._fail("start_run")
            return None

    def finish_run(self, run_id: str | None, status: str) -> None:
        if run_id is None:
            return
        try:
            self._store.finish_run(run_id, status, self._clock())
        except Exception:
            self._fail("finish_run")

    def record_outcomes(self, run_id: str | None, outcomes: list[UpsertOutcome]) -> None:
        # The guard wraps the whole body, not just the store call: building the
        # events (clock, the _RESULT_TO_EVENT subscript, Pydantic validation) is
        # just as capable of raising, and an audit trail must never be able to
        # fail the ingestion pass that feeds it.
        try:
            now = self._clock()
            events = [
                JobHistoryEvent(
                    job_id=outcome.job.id,
                    event=_RESULT_TO_EVENT[outcome.result],
                    changed_fields=outcome.changed_fields,
                    occurred_at=now,
                )
                for outcome in outcomes
                # UNCHANGED is a no-op, not history.
                if outcome.result in _RESULT_TO_EVENT
            ]
            self._write(run_id, events)
        except Exception:
            self._fail("record_outcomes")

    def record_closures(
        self,
        job_ids: list[str],
        reason: JobClosureReason,
        run_id: str | None = None,
    ) -> None:
        try:
            now = self._clock()
            self._write(
                run_id,
                [
                    JobHistoryEvent(
                        job_id=job_id,
                        event=JobHistoryEventType.CLOSED,
                        reason=reason,
                        occurred_at=now,
                    )
                    for job_id in job_ids
                ],
            )
        except Exception:
            self._fail("record_closures")

    def prune(self, cutoff: datetime) -> None:
        try:
            deleted = self._store.prune_events_older_than(cutoff)
            if deleted:
                logger.info("Pruned %d job history events older than %s", deleted, cutoff)
        except Exception:
            self._fail("prune")
            # Run pruning is deliberately skipped when event pruning failed:
            # run_id is ON DELETE SET NULL, so deleting a run whose events are
            # still there would rewrite surviving orchestrator closures to
            # run_id=NULL — indistinguishable from URL-probe sweep closures.
            return
        try:
            removed = self._store.prune_runs_without_events(cutoff)
            if removed:
                logger.info("Pruned %d ingestion runs older than %s", removed, cutoff)
        except Exception:
            self._fail("prune_runs")

    def _write(self, run_id: str | None, events: list[JobHistoryEvent]) -> None:
        if not events:
            return
        try:
            self._store.insert_events(run_id, events)
        except Exception:
            self._fail("insert_events")

    @staticmethod
    def _fail(operation: str) -> None:
        logger.exception("Job history %s failed", operation)
        get_domain_metrics().automation_failures_total.add(1, {"component": "job_history_record"})

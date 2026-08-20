from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hiresense.ingestion.domain.ingestion_run_summary import IngestionRunSummary
from hiresense.ingestion.domain.job_history_event import JobHistoryEvent


class JobHistoryPort(Protocol):
    """Persistence for the per-job audit trail and its run headers."""

    def start_run(self, trigger: str, started_at: datetime) -> str:
        """Open a run row with status 'running'. Returns its id."""
        ...

    def finish_run(self, run_id: str, status: str, finished_at: datetime) -> None:
        """Stamp a run's terminal status ('completed' or 'failed')."""
        ...

    def insert_events(self, run_id: str | None, events: list[JobHistoryEvent]) -> None:
        """Persist a batch of events in ONE bulk insert.

        `run_id` is None for closures produced outside an ingestion run (the
        URL-probe sweep). An empty list is a no-op that touches no store.
        """
        ...

    def list_events_for_job(self, job_id: str, limit: int) -> list[JobHistoryEvent]:
        """One job's events, newest first."""
        ...

    def list_events_for_run(self, run_id: str, limit: int) -> list[JobHistoryEvent]:
        """One run's events, newest first."""
        ...

    def list_runs(self, limit: int, offset: int) -> list[IngestionRunSummary]:
        """Runs newest first, each with its per-event-type totals."""
        ...

    def get_run(self, run_id: str) -> IngestionRunSummary | None: ...

    def prune_events_older_than(self, cutoff: datetime) -> int:
        """Delete events with occurred_at < cutoff. Returns the row count."""
        ...

    def prune_runs_without_events(self, cutoff: datetime) -> int:
        """Delete runs started before cutoff that have no events left.

        Must run strictly AFTER prune_events_older_than, and must never touch a
        run that still owns events: run_id is ON DELETE SET NULL, so deleting
        such a run would silently rewrite its closures to run_id=NULL and make
        them indistinguishable from URL-probe sweep closures.
        """
        ...

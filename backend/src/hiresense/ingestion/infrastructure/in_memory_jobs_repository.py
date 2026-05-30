from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.ports.jobs_repository import ScoreUpdate


class InMemoryJobsRepository:
    """In-process repository for tests and the legacy ephemeral default.

    Mirrors the SQL repository's skip-on-duplicate semantics so the two
    implementations are behaviourally interchangeable. Pruning uses an
    internal fetched_at clock since there is no DB column to consult.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, NormalizedJob] = {}
        self._dedup_to_id: dict[str, str] = {}
        self._fetched_at: dict[str, datetime] = {}

    def add_if_absent(self, job: NormalizedJob) -> bool:
        dedup_key = job.dedup_key()
        if dedup_key in self._dedup_to_id:
            return False
        self._jobs[job.id] = job
        self._dedup_to_id[dedup_key] = job.id
        self._fetched_at[job.id] = datetime.now(timezone.utc)
        return True

    def list_all(self) -> list[NormalizedJob]:
        return list(self._jobs.values())

    def get_by_id(self, job_id: str) -> NormalizedJob | None:
        return self._jobs.get(job_id)

    def update_scores(
        self,
        job_id: str,
        match_score: float | None,
        semantic_score: float | None,
    ) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        self._jobs[job_id] = job.model_copy(
            update={"match_score": match_score, "semantic_score": semantic_score}
        )

    def bulk_update_scores(self, updates: list[ScoreUpdate]) -> None:
        """Update multiple jobs' scores in one pass over the in-memory dict.

        Unknown IDs are silently skipped; an empty list is a no-op.
        """
        for update in updates:
            job = self._jobs.get(update.job_id)
            if job is None:
                continue
            self._jobs[update.job_id] = job.model_copy(
                update={
                    "match_score": update.match_score,
                    "semantic_score": update.semantic_score,
                }
            )

    def prune_older_than(self, cutoff: datetime) -> int:
        stale = [jid for jid, ts in self._fetched_at.items() if ts < cutoff]
        for jid in stale:
            job = self._jobs.pop(jid, None)
            self._fetched_at.pop(jid, None)
            if job is not None:
                self._dedup_to_id.pop(job.dedup_key(), None)
        return len(stale)

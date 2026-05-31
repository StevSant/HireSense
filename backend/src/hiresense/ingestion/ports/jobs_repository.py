from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from hiresense.ingestion.domain.models import NormalizedJob

if TYPE_CHECKING:
    from hiresense.ingestion.domain.upsert_result import UpsertResult


class JobsRepositoryPort(Protocol):
    def upsert(self, job: NormalizedJob) -> "UpsertResult":
        """Insert, update-in-place (preserving id), reopen, or no-op a job,
        keyed on stable identity `(bucket, source, identity_key)`."""
        ...

    def get_id_by_identity(self, source: str, job: NormalizedJob) -> str | None:
        """Stored row id for this job's identity, or None if absent."""
        ...

    def mark_closed(self, job_ids: list[str]) -> None:
        """Mark the given rows closed (status=closed, closed_at=now)."""
        ...

    def bump_missed_and_close(
        self, source: str, seen_identity_keys: set[str], threshold: int
    ) -> list[str]:
        """Disappearance rule for snapshot sources: increment missed_count for
        open jobs of `source` not in `seen_identity_keys`, close those reaching
        `threshold`, reset the seen ones. Returns ids closed this run."""
        ...

    def list_all(self) -> list[NormalizedJob]: ...

    def get_by_id(self, job_id: str) -> NormalizedJob | None: ...

    def update_scores(
        self,
        job_id: str,
        match_score: float | None,
        semantic_score: float | None,
    ) -> None: ...

    def prune_older_than(self, cutoff: datetime) -> int:
        """Delete rows with fetched_at < cutoff. Returns the count deleted."""
        ...

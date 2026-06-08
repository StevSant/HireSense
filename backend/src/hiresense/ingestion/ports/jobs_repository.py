from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from hiresense.ingestion.domain.models import NormalizedJob

if TYPE_CHECKING:
    from hiresense.ingestion.domain.upsert_result import UpsertResult


@dataclasses.dataclass(frozen=True)
class ScoreUpdate:
    """Immutable value object carrying a single job's score update payload.

    Both fields accept None to allow partial updates where only one signal
    is available (e.g. skill-only fallback when semantic scoring is skipped).
    """

    job_id: str
    match_score: float | None
    semantic_score: float | None


@dataclasses.dataclass(frozen=True)
class QualityUpdate:
    """Immutable value object carrying a single job's quality classification."""

    job_id: str
    quality: str
    quality_reason: str | None


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

    def find_open_stale(self, sources: list[str], limit: int) -> list[NormalizedJob]:
        """Open jobs of the given sources, oldest-checked first, capped at
        `limit` — the URL-probe revalidation sweep's work queue."""
        ...

    def mark_checked(self, job_ids: list[str]) -> None:
        """Stamp last_checked_at=now on the given rows (post-probe)."""
        ...

    def list_all(self) -> list[NormalizedJob]: ...

    def get_by_id(self, job_id: str) -> NormalizedJob | None: ...

    def update_scores(
        self,
        job_id: str,
        match_score: float | None,
        semantic_score: float | None,
    ) -> None: ...

    def bulk_update_scores(self, updates: list[ScoreUpdate]) -> None:
        """Persist score updates for multiple jobs in a single batched write.

        Unknown IDs are silently ignored. An empty list is a no-op.
        SQL implementations MUST use a single executemany bulk UPDATE keyed by
        primary key (one session, one commit) — never N individual UPDATE
        statements. In-memory implementations iterate the dict in a single pass.
        """
        ...

    def bulk_update_quality(self, updates: list["QualityUpdate"]) -> None:
        """Persist quality classifications for multiple jobs in one batched write.

        Single executemany bulk UPDATE keyed by primary key (one session, one
        commit). Unknown IDs are ignored; an empty list is a no-op.
        """
        ...

    def prune_older_than(self, cutoff: datetime) -> list[str]:
        """Delete rows with fetched_at < cutoff. Returns the deleted ids so the
        caller can evict their vector-store entries (no FK cascade)."""
        ...

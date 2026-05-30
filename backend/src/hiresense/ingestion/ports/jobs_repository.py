from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Protocol

from hiresense.ingestion.domain.models import NormalizedJob


@dataclasses.dataclass(frozen=True)
class ScoreUpdate:
    """Immutable value object carrying a single job's score update payload.

    Both fields accept None to allow partial updates where only one signal
    is available (e.g. skill-only fallback when semantic scoring is skipped).
    """

    job_id: str
    match_score: float | None
    semantic_score: float | None


class JobsRepositoryPort(Protocol):
    def add_if_absent(self, job: NormalizedJob) -> bool:
        """Insert the job if its dedup_key is not already stored.

        Returns True when the row was inserted, False when an existing row
        with the same dedup_key already exists (skipped, not updated).
        """
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

    def prune_older_than(self, cutoff: datetime) -> int:
        """Delete rows with fetched_at < cutoff. Returns the count deleted."""
        ...

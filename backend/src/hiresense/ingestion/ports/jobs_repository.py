from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hiresense.ingestion.domain.models import NormalizedJob


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

    def prune_older_than(self, cutoff: datetime) -> int:
        """Delete rows with fetched_at < cutoff. Returns the count deleted."""
        ...

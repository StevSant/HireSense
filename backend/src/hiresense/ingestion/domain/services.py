from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.normalizer import JobNormalizer
from hiresense.ingestion.ports import JobsRepositoryPort
from hiresense.kernel.events import JobsIngestedEvent

logger = logging.getLogger(__name__)


class IngestionCooldownError(Exception):
    """Raised when ingestion is triggered before the cooldown expires."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Ingestion on cooldown. Retry after {retry_after}s.")


class IngestionOrchestrator:
    def __init__(
        self,
        sources: list[Any],
        normalizers: dict[str, JobNormalizer],
        event_bus: Any,
        cooldown_seconds: int = 300,
        repository: JobsRepositoryPort | None = None,
        retention_days: int | None = None,
    ) -> None:
        self._sources = sources
        self._normalizers = normalizers
        self._event_bus = event_bus
        if repository is None:
            from hiresense.ingestion.infrastructure import InMemoryJobsRepository

            repository = InMemoryJobsRepository()
        self._repository: JobsRepositoryPort = repository
        self._cooldown_seconds = cooldown_seconds
        self._retention_days = retention_days
        self._last_run_at: float = 0.0

    async def run(
        self,
        filters: dict[str, Any] | None = None,
    ) -> list[NormalizedJob]:
        elapsed = time.monotonic() - self._last_run_at
        if self._last_run_at and elapsed < self._cooldown_seconds:
            remaining = int(self._cooldown_seconds - elapsed)
            raise IngestionCooldownError(retry_after=remaining)
        self._last_run_at = time.monotonic()

        self._prune_expired()

        new_jobs: list[NormalizedJob] = []

        for source in self._sources:
            source_name = source.source_name()
            normalizer = self._normalizers.get(source_name)
            if normalizer is None:
                logger.warning("No normalizer for source: %s", source_name)
                continue

            try:
                raw_jobs = await source.fetch_jobs(filters)
            except Exception:
                logger.exception("Failed to fetch from %s", source_name)
                continue

            for raw in raw_jobs:
                normalized_data = normalizer.normalize(raw)
                job = NormalizedJob(
                    id=str(uuid.uuid4()),
                    source=source_name,
                    source_type=source.source_type().value,
                    **normalized_data,
                )
                if self._repository.add_if_absent(job):
                    new_jobs.append(job)

        if new_jobs:
            event = JobsIngestedEvent(
                job_ids=[j.id for j in new_jobs],
                source="batch",
            )
            await self._event_bus.publish(event)

        return new_jobs

    def store_job(self, job: NormalizedJob) -> None:
        self._repository.add_if_absent(job)

    def get_job_by_id(self, job_id: str) -> NormalizedJob | None:
        return self._repository.get_by_id(job_id)

    def list_jobs(self) -> list[NormalizedJob]:
        return self._repository.list_all()

    def persist_scores(
        self,
        job_id: str,
        match_score: float | None,
        semantic_score: float | None,
    ) -> None:
        self._repository.update_scores(job_id, match_score, semantic_score)

    def _prune_expired(self) -> None:
        if not self._retention_days or self._retention_days <= 0:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        try:
            removed = self._repository.prune_older_than(cutoff)
        except Exception:
            logger.exception("Job pruning failed")
            return
        if removed:
            logger.info("Pruned %d jobs older than %s", removed, cutoff.isoformat())

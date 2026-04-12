from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.normalizer import JobNormalizer
from hiresense.kernel.contracts.ingestion import JobsIngestedEvent

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
    ) -> None:
        self._sources = sources
        self._normalizers = normalizers
        self._event_bus = event_bus
        self._jobs: dict[str, NormalizedJob] = {}
        self._cooldown_seconds = cooldown_seconds
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
        all_jobs: list[NormalizedJob] = []
        seen_dedup_keys: set[str] = set()

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
                dedup = job.dedup_key()
                if dedup not in seen_dedup_keys:
                    seen_dedup_keys.add(dedup)
                    all_jobs.append(job)
                    self._jobs[job.id] = job

        if all_jobs:
            event = JobsIngestedEvent(
                payload={
                    "job_ids": [j.id for j in all_jobs],
                    "source": "batch",
                },
            )
            await self._event_bus.publish(event)

        return all_jobs

    def store_job(self, job: NormalizedJob) -> None:
        self._jobs[job.id] = job

    def get_job_by_id(self, job_id: str) -> NormalizedJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[NormalizedJob]:
        return list(self._jobs.values())

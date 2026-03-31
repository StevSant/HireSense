from __future__ import annotations

import logging
import uuid
from typing import Any

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.normalizer import JobNormalizer
from hiresense.kernel.contracts.ingestion import JobsIngestedEvent

logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    def __init__(
        self,
        sources: list[Any],
        normalizers: dict[str, JobNormalizer],
        event_bus: Any,
    ) -> None:
        self._sources = sources
        self._normalizers = normalizers
        self._event_bus = event_bus

    async def run(
        self,
        filters: dict[str, Any] | None = None,
    ) -> list[NormalizedJob]:
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

        if all_jobs:
            event = JobsIngestedEvent(
                payload={
                    "job_ids": [j.id for j in all_jobs],
                    "source": "batch",
                },
            )
            await self._event_bus.publish(event)

        return all_jobs

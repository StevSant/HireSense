from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.normalizer import JobNormalizer
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.kernel.events import JobsIngestedEvent

logger = logging.getLogger(__name__)


class ScanFilters(BaseModel):
    categories: list[str] = []
    companies: list[str] = []
    keyword: str | None = None


class ScanError(BaseModel):
    portal: str
    platform: str
    error: str


class ScanResult(BaseModel):
    total_fetched: int
    new: int
    duplicates: int
    jobs: list[NormalizedJob]
    errors: list[ScanError]


class PortalScanner:
    def __init__(
        self,
        config: PortalsConfig,
        adapters: dict[str, Any],
        normalizers: dict[str, JobNormalizer],
        event_bus: Any,
    ) -> None:
        self._config = config
        self._adapters = adapters
        self._normalizers = normalizers
        self._event_bus = event_bus
        self._jobs: dict[str, NormalizedJob] = {}

    def list_jobs(self) -> list[NormalizedJob]:
        return list(self._jobs.values())

    def _filter_portals(self, filters: ScanFilters) -> list[PortalEntry]:
        portals = self._config.portals
        portals = [p for p in portals if p.enabled]

        if filters.categories:
            filter_set = set(filters.categories)
            portals = [p for p in portals if filter_set & set(p.categories)]

        if filters.companies:
            company_set = set(filters.companies)
            portals = [p for p in portals if p.name in company_set]

        return portals

    async def scan(self, filters: ScanFilters) -> ScanResult:
        portals = self._filter_portals(filters)
        seen_dedup_keys: set[str] = set()
        new_jobs: list[NormalizedJob] = []
        errors: list[ScanError] = []
        total_fetched = 0

        for portal in portals:
            adapter = self._adapters.get(portal.platform)
            normalizer = self._normalizers.get(portal.platform)

            if adapter is None:
                logger.warning("No adapter for platform: %s", portal.platform)
                continue
            if normalizer is None:
                logger.warning("No normalizer for platform: %s", portal.platform)
                continue

            try:
                raw_jobs = await adapter.fetch_jobs(portal.board_id, portal.name)
            except Exception as exc:
                errors.append(
                    ScanError(
                        portal=portal.name,
                        platform=portal.platform,
                        error=str(exc),
                    )
                )
                continue

            for raw in raw_jobs:
                total_fetched += 1
                normalized_data = normalizer.normalize(raw)
                job = NormalizedJob(
                    id=str(uuid.uuid4()),
                    source=portal.name,
                    source_type="api",
                    platform=portal.platform,
                    categories=list(portal.categories),
                    **normalized_data,
                )
                if filters.keyword:
                    kw = filters.keyword.lower()
                    if kw not in job.title.lower() and kw not in job.description.lower():
                        continue

                dedup_key = job.dedup_key()
                if dedup_key not in seen_dedup_keys:
                    seen_dedup_keys.add(dedup_key)
                    new_jobs.append(job)
                    self._jobs[job.id] = job

        duplicates = total_fetched - len(new_jobs)

        if new_jobs:
            event = JobsIngestedEvent(
                job_ids=[j.id for j in new_jobs],
                source="portal_scan",
            )
            await self._event_bus.publish(event)

        return ScanResult(
            total_fetched=total_fetched,
            new=len(new_jobs),
            duplicates=duplicates,
            jobs=new_jobs,
            errors=errors,
        )

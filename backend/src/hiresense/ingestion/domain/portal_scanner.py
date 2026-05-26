from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.normalizer import JobNormalizer
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.ports import JobsRepositoryPort
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
        repository: JobsRepositoryPort | None = None,
        retention_days: int | None = None,
    ) -> None:
        self._config = config
        self._adapters = adapters
        self._normalizers = normalizers
        self._event_bus = event_bus
        if repository is None:
            from hiresense.ingestion.infrastructure import InMemoryJobsRepository

            repository = InMemoryJobsRepository()
        self._repository: JobsRepositoryPort = repository
        self._retention_days = retention_days

    def list_jobs(self) -> list[NormalizedJob]:
        return self._repository.list_all()

    def get_job_by_id(self, job_id: str) -> NormalizedJob | None:
        return self._repository.get_by_id(job_id)

    def persist_scores(
        self,
        job_id: str,
        match_score: float | None,
        semantic_score: float | None,
    ) -> None:
        self._repository.update_scores(job_id, match_score, semantic_score)

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
            logger.info("Pruned %d portal jobs older than %s", removed, cutoff.isoformat())

    async def scan(self, filters: ScanFilters) -> ScanResult:
        self._prune_expired()

        portals = self._filter_portals(filters)
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

                if self._repository.add_if_absent(job):
                    new_jobs.append(job)

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

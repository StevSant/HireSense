from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from hiresense.ingestion.domain.identity import identity_key
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.normalizer import JobNormalizer
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.ports import JobsRepositoryPort
from hiresense.ingestion.ports.jobs_repository import ScoreUpdate
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
        repository: JobsRepositoryPort,
        retention_days: int | None = None,
        indexer: Any | None = None,
        closure_miss_threshold: int = 2,
    ) -> None:
        self._config = config
        self._adapters = adapters
        self._normalizers = normalizers
        self._event_bus = event_bus
        self._repository: JobsRepositoryPort = repository
        self._retention_days = retention_days
        self._indexer = indexer
        self._closure_miss_threshold = closure_miss_threshold

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

    def persist_scores_batch(self, updates: list[ScoreUpdate]) -> None:
        """Persist score updates for multiple jobs in a single batched write.

        Delegates directly to repo.bulk_update_scores so the call site
        executes one I/O round-trip regardless of corpus size.
        """
        self._repository.bulk_update_scores(updates)

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

            seen_keys: set[str] = set()
            touched: list[NormalizedJob] = []
            for raw in raw_jobs:
                total_fetched += 1
                normalized_data = normalizer.normalize(raw)
                job = NormalizedJob(
                    id=str(uuid.uuid4()),
                    source=portal.name,
                    source_type="api",
                    source_id=raw.source_id,
                    platform=portal.platform,
                    categories=list(portal.categories),
                    **normalized_data,
                )
                if filters.keyword:
                    kw = filters.keyword.lower()
                    if kw not in job.title.lower() and kw not in job.description.lower():
                        continue

                existing_id = self._repository.get_id_by_identity(portal.name, job)
                if existing_id:
                    job = job.model_copy(update={"id": existing_id})
                seen_keys.add(identity_key(job))
                result = self._repository.upsert(job)
                if result in (
                    UpsertResult.INSERTED,
                    UpsertResult.UPDATED,
                    UpsertResult.REOPENED,
                ):
                    touched.append(job)
                    if result == UpsertResult.INSERTED:
                        new_jobs.append(job)

            if touched and self._indexer is not None:
                await self._indexer.index(touched)

            # Disappearance closure: snapshot portals only, and never during a
            # keyword-filtered scan (that is not a complete snapshot of the board).
            if adapter.supports_snapshot_closure() and not filters.keyword:
                closed_ids = self._repository.bump_missed_and_close(
                    portal.name, seen_keys, self._closure_miss_threshold
                )
                if closed_ids and self._indexer is not None:
                    await self._indexer.remove(closed_ids)

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

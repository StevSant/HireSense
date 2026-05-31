from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from hiresense.ingestion.domain.identity import identity_key
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.normalizer import JobNormalizer
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.ports import JobsRepositoryPort
from hiresense.ingestion.ports.jobs_repository import ScoreUpdate
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
        repository: JobsRepositoryPort,
        cooldown_seconds: int = 300,
        retention_days: int | None = None,
        indexer: Any | None = None,
        closure_miss_threshold: int = 2,
    ) -> None:
        self._sources = sources
        self._normalizers = normalizers
        self._event_bus = event_bus
        self._repository: JobsRepositoryPort = repository
        self._cooldown_seconds = cooldown_seconds
        self._retention_days = retention_days
        self._indexer = indexer
        self._closure_miss_threshold = closure_miss_threshold
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

        await self._prune_expired()

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
                continue  # bad fetch: skip disappearance for this source this run

            seen_keys: set[str] = set()
            touched: list[NormalizedJob] = []
            for raw in raw_jobs:
                normalized_data = normalizer.normalize(raw)
                job = NormalizedJob(
                    id=str(uuid.uuid4()),
                    source=source_name,
                    source_type=source.source_type().value,
                    source_id=raw.source_id,
                    **normalized_data,
                )
                existing_id = self._repository.get_id_by_identity(source_name, job)
                if existing_id:
                    job = job.model_copy(update={"id": existing_id})
                seen_keys.add(identity_key(job))
                result = self._repository.upsert(job)
                # INSERTED/UPDATED/REOPENED all need (re-)indexing; REOPENED matters
                # because closure removed the job from the vector store.
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

            # Disappearance-based closure: only for snapshot sources, only after a
            # successful fetch (errored fetches `continue` above and never reach here).
            if source.supports_snapshot_closure():
                closed_ids = self._repository.bump_missed_and_close(
                    source_name, seen_keys, self._closure_miss_threshold
                )
                if closed_ids and self._indexer is not None:
                    await self._indexer.remove(closed_ids)

        # Indexing already happened per-source via `touched` (inserted/updated/
        # reopened). Here we only announce the newly inserted jobs.
        if new_jobs:
            event = JobsIngestedEvent(
                job_ids=[j.id for j in new_jobs],
                source="batch",
            )
            await self._event_bus.publish(event)

        return new_jobs

    def store_job(self, job: NormalizedJob) -> None:
        self._repository.upsert(job)

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

    def persist_scores_batch(self, updates: list[ScoreUpdate]) -> None:
        """Persist score updates for multiple jobs in a single batched write.

        Delegates directly to repo.bulk_update_scores so the call site
        executes one I/O round-trip regardless of corpus size.
        """
        self._repository.bulk_update_scores(updates)

    async def _prune_expired(self) -> None:
        if not self._retention_days or self._retention_days <= 0:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        try:
            removed_ids = self._repository.prune_older_than(cutoff)
        except Exception:
            logger.exception("Job pruning failed")
            return
        if removed_ids:
            logger.info("Pruned %d jobs older than %s", len(removed_ids), cutoff.isoformat())
            if self._indexer is not None:
                try:
                    await self._indexer.remove(removed_ids)  # evict orphan vectors
                except Exception:
                    logger.exception("Failed to evict pruned job vectors")

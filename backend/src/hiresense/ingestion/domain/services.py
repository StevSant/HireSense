from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from pydantic import BaseModel

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.normalizer import JobNormalizer
from hiresense.kernel.events import JobsIngestedEvent

logger = logging.getLogger(__name__)


class SourceResult(BaseModel):
    """Per-source outcome of a single ingestion run."""

    source: str
    status: str  # "ok" | "error" | "skipped"
    fetched: int = 0
    error: str | None = None


class IngestionCooldownError(Exception):
    """Raised when ingestion is triggered before the cooldown expires."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Ingestion on cooldown. Retry after {retry_after}s.")


class IngestionCancelledError(Exception):
    """Raised when an in-flight ingestion is cancelled by the user.

    Carries any jobs that had already been normalized before the cancel
    signal was observed, so the caller can decide whether to return a
    partial result to the client.
    """

    def __init__(
        self,
        partial_jobs: list[NormalizedJob],
        source_results: list[SourceResult] | None = None,
    ) -> None:
        self.partial_jobs = partial_jobs
        self.source_results = source_results or []
        super().__init__("Ingestion cancelled.")


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
        self._cancel_event: asyncio.Event | None = None
        self._last_source_results: list[SourceResult] = []

    def get_last_source_results(self) -> list[SourceResult]:
        return list(self._last_source_results)

    async def run(
        self,
        filters: dict[str, Any] | None = None,
    ) -> list[NormalizedJob]:
        elapsed = time.monotonic() - self._last_run_at
        if self._last_run_at and elapsed < self._cooldown_seconds:
            remaining = int(self._cooldown_seconds - elapsed)
            raise IngestionCooldownError(retry_after=remaining)
        self._last_run_at = time.monotonic()
        self._cancel_event = asyncio.Event()
        results: list[SourceResult] = []
        try:
            return await self._run_inner(filters, results)
        except IngestionCancelledError as exc:
            # Reset cooldown so the user can immediately retry after cancelling
            # (they explicitly chose to stop, usually to change filters/source).
            self._last_run_at = 0.0
            exc.source_results = list(results)
            if exc.partial_jobs:
                await self._publish(exc.partial_jobs)
            raise
        finally:
            self._cancel_event = None
            self._last_source_results = list(results)

    async def _run_inner(
        self,
        filters: dict[str, Any] | None,
        results: list[SourceResult],
    ) -> list[NormalizedJob]:
        all_jobs: list[NormalizedJob] = []
        seen_dedup_keys: set[str] = set()
        lock = asyncio.Lock()
        assert self._cancel_event is not None

        # Sources run concurrently so the UI can show jobs from fast sources
        # while slow ones are still in flight. Shared state (the dedup set,
        # the in-memory job store, and the results list) is mutated only
        # under the lock — the critical section is tiny (dict check + insert)
        # so contention stays negligible.
        gather_results = await asyncio.gather(
            *(
                self._run_source(
                    source, filters, all_jobs, seen_dedup_keys, results, lock
                )
                for source in self._sources
            ),
            return_exceptions=True,
        )

        # Preserve the old "first unexpected error aborts the run" semantics,
        # but only after all siblings have had a chance to finish (or to
        # observe cancel themselves).
        for r in gather_results:
            if isinstance(r, Exception) and not self._cancel_event.is_set():
                raise r

        if self._cancel_event.is_set():
            raise IngestionCancelledError(all_jobs, results)

        if all_jobs:
            await self._publish(all_jobs)

        return all_jobs

    async def _run_source(
        self,
        source: Any,
        filters: dict[str, Any] | None,
        all_jobs: list[NormalizedJob],
        seen_dedup_keys: set[str],
        results: list[SourceResult],
        lock: asyncio.Lock,
    ) -> None:
        assert self._cancel_event is not None
        if self._cancel_event.is_set():
            return

        source_name = source.source_name()
        normalizer = self._normalizers.get(source_name)
        if normalizer is None:
            logger.warning("No normalizer for source: %s", source_name)
            async with lock:
                results.append(
                    SourceResult(
                        source=source_name,
                        status="skipped",
                        error="No normalizer registered",
                    )
                )
            return

        try:
            raw_jobs = await source.fetch_jobs(filters)
        except Exception as exc:
            logger.exception("Failed to fetch from %s", source_name)
            async with lock:
                results.append(
                    SourceResult(source=source_name, status="error", error=str(exc))
                )
            return

        source_count = 0
        for raw in raw_jobs:
            if self._cancel_event.is_set():
                async with lock:
                    results.append(
                        SourceResult(
                            source=source_name, status="ok", fetched=source_count
                        )
                    )
                return
            normalized_data = normalizer.normalize(raw)
            job = NormalizedJob(
                id=str(uuid.uuid4()),
                source=source_name,
                source_type=source.source_type().value,
                **normalized_data,
            )
            dedup = job.dedup_key()
            async with lock:
                if dedup not in seen_dedup_keys:
                    seen_dedup_keys.add(dedup)
                    all_jobs.append(job)
                    self._jobs[job.id] = job
                    source_count += 1

        async with lock:
            results.append(
                SourceResult(source=source_name, status="ok", fetched=source_count)
            )

    async def _publish(self, jobs: list[NormalizedJob]) -> None:
        event = JobsIngestedEvent(
            job_ids=[j.id for j in jobs],
            source="batch",
        )
        await self._event_bus.publish(event)

    def cancel(self) -> bool:
        """Signal the currently running ingestion to stop. No-op if idle."""
        if self._cancel_event is None:
            return False
        self._cancel_event.set()
        return True

    def is_active(self) -> bool:
        return self._cancel_event is not None

    def store_job(self, job: NormalizedJob) -> None:
        self._jobs[job.id] = job

    def get_job_by_id(self, job_id: str) -> NormalizedJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[NormalizedJob]:
        return list(self._jobs.values())

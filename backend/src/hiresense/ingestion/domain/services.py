from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from opentelemetry import trace

from hiresense.ingestion.domain.application_classifier import classify_application
from hiresense.ingestion.domain.identity import identity_key
from hiresense.ingestion.domain.job_list_criteria import JobListCriteria
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.work_authorization_facts import add_work_authorization_facts
from hiresense.ingestion.domain.normalizer import JobNormalizer
from hiresense.ingestion.domain.source_health import SourceHealthTracker, SourceRunStats
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.ports import JobsRepositoryPort
from hiresense.ingestion.ports.jobs_repository import QualityUpdate, ScoreUpdate
from hiresense.kernel.events import JobsIngestedEvent
from hiresense.observability import get_domain_metrics, get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer("hiresense.ingestion")


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
        quality_classifier: Any | None = None,
        health_tracker: SourceHealthTracker | None = None,
    ) -> None:
        self._sources = sources
        self._normalizers = normalizers
        self._event_bus = event_bus
        self._repository: JobsRepositoryPort = repository
        self._cooldown_seconds = cooldown_seconds
        self._retention_days = retention_days
        self._indexer = indexer
        self._closure_miss_threshold = closure_miss_threshold
        self._quality_classifier = quality_classifier
        self._health = health_tracker or SourceHealthTracker()
        self._last_run_at: float = 0.0
        # Single-flight guard: True while a run() is mid-pass. Prevents two
        # concurrent /fetch triggers from both clearing the cooldown check and
        # double-running the ingestion pass (#159).
        self._run_in_flight: bool = False

    @property
    def health_tracker(self) -> SourceHealthTracker:
        return self._health

    def source_names(self) -> list[str]:
        return [s.source_name() for s in self._sources]

    async def run(
        self,
        filters: dict[str, Any] | None = None,
    ) -> list[NormalizedJob]:
        _metrics = get_domain_metrics()
        with _tracer.start_as_current_span("ingestion.run") as span:
            started = time.perf_counter()
            claimed = False
            try:
                # Single-flight + cooldown gate. The in-flight check, the
                # cooldown check, and the claim below all run with no intervening
                # await, so on the single-threaded event loop they are atomic: a
                # second concurrent /fetch can neither double-run a pass already
                # in flight nor slip past the cooldown window (#159).
                if self._run_in_flight:
                    raise IngestionCooldownError(retry_after=self._cooldown_seconds)
                elapsed = time.monotonic() - self._last_run_at
                if self._last_run_at and elapsed < self._cooldown_seconds:
                    remaining = int(self._cooldown_seconds - elapsed)
                    raise IngestionCooldownError(retry_after=remaining)
                self._run_in_flight = True
                claimed = True

                await self._prune_expired()

                new_jobs: list[NormalizedJob] = []
                all_touched: list[NormalizedJob] = []

                for source in self._sources:
                    source_name = source.source_name()
                    normalizer = self._normalizers.get(source_name)
                    if normalizer is None:
                        logger.warning("No normalizer for source: %s", source_name)
                        continue

                    fetch_started = time.perf_counter()
                    run_stats = SourceRunStats()
                    with _tracer.start_as_current_span("ingestion.source.fetch") as fetch_span:
                        fetch_span.set_attribute("source", source_name)
                        try:
                            raw_jobs = await source.fetch_jobs(filters)
                        except Exception as exc:
                            fetch_span.set_status(trace.Status(trace.StatusCode.ERROR))
                            logger.exception("Failed to fetch from %s", source_name)
                            raw_jobs = None
                            run_stats.success = False
                            run_stats.error = f"{type(exc).__name__}: {exc}"
                        finally:
                            duration_ms = (time.perf_counter() - fetch_started) * 1000.0
                            _metrics.source_fetch_duration_ms.record(
                                duration_ms,
                                {"source": source_name},
                            )
                    if raw_jobs is None:
                        self._health.record_run(
                            source_name,
                            duration_ms=(time.perf_counter() - fetch_started) * 1000.0,
                            stats=run_stats,
                        )
                        continue  # bad fetch: skip disappearance for this source this run

                    fetched_count = len(raw_jobs)
                    run_stats.pages_fetched = getattr(source, "last_pages_fetched", 0) or 0
                    run_stats.jobs_discovered = fetched_count
                    run_stats.jobs_rejected_malformed = int(
                        getattr(source, "last_rejected_malformed", 0) or 0
                    )
                    run_stats.rate_limited_count = int(
                        getattr(source, "last_rate_limited_count", 0) or 0
                    )
                    run_stats.parse_failures = int(getattr(source, "last_parse_failures", 0) or 0)
                    _metrics.jobs_fetched_total.add(fetched_count, {"source": source_name})

                    normalized: list[NormalizedJob] = []
                    for raw in raw_jobs:
                        try:
                            normalized_data = add_work_authorization_facts(
                                normalizer.normalize(raw)
                            )
                        except Exception:
                            run_stats.jobs_rejected_malformed += 1
                            logger.exception(
                                "Failed to normalize job from %s id=%s",
                                source_name,
                                raw.source_id,
                            )
                            continue
                        if not normalized_data.get("title") or not normalized_data.get("company"):
                            run_stats.jobs_rejected_malformed += 1
                            continue
                        classification = classify_application(
                            normalized_data.get("url"),
                            platform=normalized_data.get("platform"),
                        )
                        normalized.append(
                            NormalizedJob(
                                id=str(uuid.uuid4()),
                                source=source_name,
                                source_type=source.source_type().value,
                                source_id=raw.source_id,
                                apply_url=classification.apply_url,
                                application_method=classification.application_method,
                                ats_type=classification.ats_type,
                                **normalized_data,
                            )
                        )

                    # One bulk identity lookup + one commit per source instead
                    # of 2 queries per job. Outcomes carry the resolved ids.
                    outcomes = await asyncio.to_thread(self._repository.bulk_upsert, normalized)
                    seen_keys = {identity_key(o.job) for o in outcomes}
                    touched: list[NormalizedJob] = []
                    for outcome in outcomes:
                        # INSERTED/UPDATED/REOPENED all need (re-)indexing; REOPENED matters
                        # because closure removed the job from the vector store.
                        if outcome.result in (
                            UpsertResult.INSERTED,
                            UpsertResult.UPDATED,
                            UpsertResult.REOPENED,
                        ):
                            touched.append(outcome.job)
                            if outcome.result == UpsertResult.INSERTED:
                                new_jobs.append(outcome.job)
                                run_stats.jobs_created += 1
                            else:
                                run_stats.jobs_updated += 1
                        else:
                            run_stats.jobs_deduplicated += 1

                    indexed_count = len(touched)
                    _metrics.jobs_indexed_total.add(indexed_count, {"source": source_name})

                    if touched and self._indexer is not None:
                        await self._indexer.index(touched)

                    all_touched.extend(touched)

                    # Disappearance-based closure: only for snapshot sources, only after a
                    # successful fetch (errored fetches `continue` above and never reach here).
                    if source.supports_snapshot_closure():
                        closed_ids = await asyncio.to_thread(
                            self._repository.bump_missed_and_close,
                            source_name,
                            seen_keys,
                            self._closure_miss_threshold,
                        )
                        if closed_ids and self._indexer is not None:
                            await self._indexer.remove(closed_ids)

                    self._health.record_run(
                        source_name,
                        duration_ms=(time.perf_counter() - fetch_started) * 1000.0,
                        stats=run_stats,
                    )

                # Quality classification (intrinsic, profile-independent) for
                # every inserted/updated/reopened job, in one batched pass.
                # Failures degrade to leaving the job at its default "ok".
                if all_touched and self._quality_classifier is not None:
                    try:
                        verdicts = await self._quality_classifier.classify(all_touched)
                        if verdicts:
                            await asyncio.to_thread(
                                self._repository.bulk_update_quality,
                                [
                                    QualityUpdate(v.job_id, v.quality.value, v.reason)
                                    for v in verdicts.values()
                                ],
                            )
                    except Exception:
                        logger.exception("Job-quality classification failed; left as 'ok'")

                # Indexing already happened per-source via `touched` (inserted/updated/
                # reopened). Here we only announce the newly inserted jobs.
                if new_jobs:
                    event = JobsIngestedEvent(
                        job_ids=[j.id for j in new_jobs],
                        source="batch",
                    )
                    await self._event_bus.publish(event)

                span.set_attribute("ingestion.jobs_new", len(new_jobs))
                _metrics.ingestion_run_duration_ms.record((time.perf_counter() - started) * 1000.0)
                # Start the cooldown only after a fully successful pass, so a run
                # that fails fast doesn't consume the window (#159).
                self._last_run_at = time.monotonic()
                return new_jobs
            except IngestionCooldownError:
                # Normal throttling, not an error — leave span status unset.
                raise
            except Exception:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                raise
            finally:
                # Release the single-flight guard only if this call claimed it —
                # a cooldown-rejected concurrent trigger must not clear the flag
                # held by the run that is actually in flight.
                if claimed:
                    self._run_in_flight = False

    def store_job(self, job: NormalizedJob) -> None:
        self._repository.upsert(job)

    def get_job_by_id(self, job_id: str) -> NormalizedJob | None:
        return self._repository.get_by_id(job_id)

    def get_jobs_by_ids(self, job_ids: list[str]) -> dict[str, NormalizedJob]:
        """Batch job enrichment: resolve many ids in one query (avoids the
        per-row ``get_job_by_id`` N+1 when shaping list responses)."""
        return self._repository.get_by_ids(job_ids)

    def list_jobs(self, criteria: JobListCriteria | None = None) -> list[NormalizedJob]:
        """Full corpus, or — given criteria — only rows matching the cheap
        selective predicates (filtered DB-side by the SQL repository)."""
        if criteria is None:
            return self._repository.list_all()
        return self._repository.list_filtered(criteria)

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
            removed_ids = await asyncio.to_thread(self._repository.prune_older_than, cutoff)
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

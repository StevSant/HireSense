from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from hiresense.ingestion.domain.embedding_text import job_text, job_text_hash
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.shared.observability import get_domain_metrics

logger = logging.getLogger(__name__)


class JobEmbeddingIndexer:
    """Embeds newly ingested jobs and upserts them into the vector store.

    Wired per bucket ("boards" / "portals") so semantic search can filter by tab
    via the stored metadata. Embedding/upsert failures are logged, never raised —
    a missing embedding must not fail ingestion. Returns the count actually
    indexed so callers can surface coverage (no silent drops).

    Every swallowed failure also increments
    ``automation_failures_total{component=job_embedding_*}``, because a log line
    alone is not a signal anyone watches: an un-indexed job never enters semantic
    search and nothing retries it, so the only cure is a manual
    ``POST /ingestion/backfill-embeddings``.
    """

    def __init__(self, embedding: Any, vector_store: Any, *, bucket: str) -> None:
        self._embedding = embedding
        self._vector_store = vector_store
        self._bucket = bucket

    async def index(self, jobs: list[NormalizedJob]) -> int:
        if not jobs:
            return 0
        hashes = {job.id: job_text_hash(job) for job in jobs}
        stale = await self._select_stale(jobs, hashes)
        skipped = len(jobs) - len(stale)
        if skipped:
            # Embedding is by far the most expensive step of an ingestion pass
            # (seconds per batch of 32 on CPU), and a job whose embedded text is
            # unchanged — the common case, including a close/reopen round trip —
            # would otherwise be re-encoded to produce the identical vector.
            logger.info(
                "Job embedding: %d of %d job(s) already current, re-embedding %d",
                skipped,
                len(jobs),
                len(stale),
            )
        if not stale:
            return 0

        texts = [job_text(j) for j in stale]
        try:
            vectors = await self._embedding.embed(texts)
        except Exception:
            logger.exception(
                "Job embedding batch failed (size=%d) — none of these jobs will appear in "
                "semantic search until POST /ingestion/backfill-embeddings is run",
                len(stale),
            )
            get_domain_metrics().automation_failures_total.add(
                1, {"component": "job_embedding_index"}
            )
            return 0

        jobs = stale
        indexed = 0
        empty = 0
        pending: list[tuple[str, list[float], dict[str, Any]]] = []
        for job, vec in zip(jobs, vectors):
            if not vec:
                empty += 1
                continue
            pending.append(
                (
                    job.id,
                    vec,
                    {
                        "bucket": self._bucket,
                        "source": job.source,
                        "text_hash": hashes[job.id],
                    },
                )
            )

        indexed = await self._upsert_pending(pending)
        if empty:
            # The embedding port handed back blanks. Silently skipping them left
            # no trace at all, so a degraded model looked like a clean run.
            logger.warning(
                "Job embedding returned %d empty vector(s) of %d — those jobs stay out of "
                "semantic search",
                empty,
                len(jobs),
            )
        return indexed

    async def _upsert_pending(self, items: list[tuple[str, list[float], dict[str, Any]]]) -> int:
        if not items:
            return 0

        bulk_upsert: (
            Callable[[list[tuple[str, list[float], dict[str, Any]]]], Awaitable[None]] | None
        ) = getattr(self._vector_store, "upsert_many", None)
        if callable(bulk_upsert):
            try:
                await bulk_upsert(items)
                return len(items)
            except Exception:
                # Keep the old per-vector recovery path for a partial adapter or
                # a transient bulk failure. A single bad row should not hide all
                # other embeddings from semantic search.
                logger.exception(
                    "Bulk vector upsert failed (size=%d); retrying individually",
                    len(items),
                )

        indexed = 0
        for job_id, vector, metadata in items:
            try:
                await self._vector_store.upsert(job_id, vector, metadata)
                indexed += 1
            except Exception:
                logger.exception("Vector upsert failed for job %s", job_id)
                get_domain_metrics().automation_failures_total.add(
                    1, {"component": "job_embedding_upsert"}
                )
        return indexed

    async def _select_stale(
        self, jobs: list[NormalizedJob], hashes: dict[str, str]
    ) -> list[NormalizedJob]:
        """The subset of ``jobs`` whose stored vector is missing or out of date.

        Stores that predate ``get_metadata`` (simple in-memory ones) return every
        job, preserving the original always-embed behaviour rather than silently
        skipping work they cannot verify. A stored vector with no ``text_hash``
        is likewise treated as stale, so the first pass after this change
        backfills the hash instead of trusting an unlabelled vector.
        """
        reader = getattr(self._vector_store, "get_metadata", None)
        if reader is None:
            return jobs
        try:
            stored = await reader([j.id for j in jobs])
        except Exception:
            logger.exception(
                "Vector metadata lookup failed — re-embedding all %d job(s)", len(jobs)
            )
            return jobs
        return [j for j in jobs if (stored.get(j.id) or {}).get("text_hash") != hashes[j.id]]

    async def remove(self, job_ids: list[str]) -> None:
        """Drop closed jobs from the vector store so they leave semantic search.

        Failures are logged, never raised — a stale vector entry must not fail
        ingestion. Nothing re-attempts the delete, though, so a failure means
        closed jobs keep being returned by ANN search: count it as an automation
        failure rather than leaving it to a log nobody tails."""
        if not job_ids:
            return
        try:
            await self._vector_store.delete(job_ids)
        except Exception:
            logger.exception(
                "Vector delete failed (n=%d) — these closed jobs stay in semantic search results",
                len(job_ids),
            )
            get_domain_metrics().automation_failures_total.add(
                1, {"component": "job_embedding_delete"}
            )

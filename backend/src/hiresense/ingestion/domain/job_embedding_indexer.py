from __future__ import annotations

import logging
from typing import Any

from hiresense.ingestion.domain.embedding_text import job_text
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.observability import get_domain_metrics

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
        texts = [job_text(j) for j in jobs]
        try:
            vectors = await self._embedding.embed(texts)
        except Exception:
            logger.exception(
                "Job embedding batch failed (size=%d) — none of these jobs will appear in "
                "semantic search until POST /ingestion/backfill-embeddings is run",
                len(jobs),
            )
            get_domain_metrics().automation_failures_total.add(
                1, {"component": "job_embedding_index"}
            )
            return 0

        indexed = 0
        empty = 0
        for job, vec in zip(jobs, vectors):
            if not vec:
                empty += 1
                continue
            try:
                await self._vector_store.upsert(
                    job.id,
                    vec,
                    {"bucket": self._bucket, "source": job.source},
                )
                indexed += 1
            except Exception:
                logger.exception("Vector upsert failed for job %s", job.id)
                get_domain_metrics().automation_failures_total.add(
                    1, {"component": "job_embedding_upsert"}
                )
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

from __future__ import annotations

import logging
from typing import Any

from hiresense.ingestion.domain.embedding_text import job_text
from hiresense.ingestion.domain.models import NormalizedJob

logger = logging.getLogger(__name__)


class JobEmbeddingIndexer:
    """Embeds newly ingested jobs and upserts them into the vector store.

    Wired per bucket ("boards" / "portals") so semantic search can filter by tab
    via the stored metadata. Embedding/upsert failures are logged, never raised —
    a missing embedding must not fail ingestion. Returns the count actually
    indexed so callers can surface coverage (no silent drops).
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
            logger.exception("Job embedding batch failed (size=%d)", len(jobs))
            return 0

        indexed = 0
        for job, vec in zip(jobs, vectors):
            if not vec:
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
        return indexed

    async def remove(self, job_ids: list[str]) -> None:
        """Drop closed jobs from the vector store so they leave semantic search.

        Failures are logged, never raised — a stale vector entry must not fail
        ingestion (it just lingers until the next sweep)."""
        if not job_ids:
            return
        try:
            await self._vector_store.delete(job_ids)
        except Exception:
            logger.exception("Vector delete failed (n=%d)", len(job_ids))

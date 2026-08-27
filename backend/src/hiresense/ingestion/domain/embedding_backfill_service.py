from __future__ import annotations

import logging
from dataclasses import dataclass

from hiresense.ingestion.domain.embedding_text import job_text
from hiresense.ingestion.domain.job_list_criteria import JobListCriteria
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.ports.jobs_repository import JobsRepositoryPort
from hiresense.shared.ports.embedding import EmbeddingPort
from hiresense.shared.ports.vector_store import VectorStorePort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackfillResult:
    boards: int
    portals: int

    @property
    def total(self) -> int:
        return self.boards + self.portals


class EmbeddingBackfillService:
    """Re-embeds all existing jobs from both buckets into the vector store.

    Idempotent: upsert semantics mean re-running replaces vectors in place
    without duplicating entries. Safe to call multiple times.

    Used by POST /ingestion/backfill-embeddings — the authenticated operator
    triggers this when pre-existing rows need to be indexed into pgvector so
    the SemanticPreRanker can surface them.
    """

    def __init__(
        self,
        *,
        boards_repo: JobsRepositoryPort,
        portals_repo: JobsRepositoryPort,
        embedding: EmbeddingPort,
        vector_store: VectorStorePort | None,
        chunk_size: int = 256,
    ) -> None:
        self._boards_repo = boards_repo
        self._portals_repo = portals_repo
        self._embedding = embedding
        self._vector_store = vector_store
        self._chunk_size = max(1, chunk_size)

    async def run(self) -> BackfillResult:
        """Embed + upsert open jobs in both buckets. Returns per-bucket counts."""
        if self._vector_store is None:
            logger.warning("EmbeddingBackfillService: vector store not configured, skipping")
            return BackfillResult(boards=0, portals=0)

        # Open-only, filtered DB-side; low-quality jobs are still indexed
        # (quality is a display concern, not an embedding one).
        open_only = JobListCriteria(include_closed=False, include_low_quality=True)
        boards_jobs = self._boards_repo.list_filtered(open_only)
        portals_jobs = self._portals_repo.list_filtered(open_only)

        boards_count = await self._backfill_bucket(boards_jobs, bucket="boards")
        portals_count = await self._backfill_bucket(portals_jobs, bucket="portals")
        return BackfillResult(boards=boards_count, portals=portals_count)

    async def _backfill_bucket(self, jobs: list[NormalizedJob], *, bucket: str) -> int:
        if not jobs:
            return 0

        indexed = 0
        for start in range(0, len(jobs), self._chunk_size):
            chunk = jobs[start : start + self._chunk_size]
            texts = [job_text(j) for j in chunk]
            try:
                vectors = await self._embedding.embed(texts)
            except Exception:
                logger.exception(
                    "Backfill embedding batch failed (bucket=%s, size=%d)",
                    bucket,
                    len(chunk),
                )
                continue

            items = [
                (job.id, vec, {"bucket": bucket, "source": job.source})
                for job, vec in zip(chunk, vectors)
                if vec
            ]
            indexed += await self._upsert_chunk(items, bucket=bucket)

        logger.info("Backfill indexed %d/%d jobs (bucket=%s)", indexed, len(jobs), bucket)
        return indexed

    async def _upsert_chunk(
        self,
        items: list[tuple[str, list[float], dict[str, str]]],
        *,
        bucket: str,
    ) -> int:
        if not items or self._vector_store is None:
            return 0

        bulk_upsert = getattr(self._vector_store, "upsert_many", None)
        if callable(bulk_upsert):
            try:
                await bulk_upsert(items)
                return len(items)
            except Exception:
                logger.exception(
                    "Backfill bulk vector upsert failed (bucket=%s, size=%d); "
                    "retrying individually",
                    bucket,
                    len(items),
                )

        indexed = 0
        for job_id, vector, metadata in items:
            try:
                await self._vector_store.upsert(job_id, vector, metadata)
                indexed += 1
            except Exception:
                logger.exception("Backfill vector upsert failed for job %s", job_id)
        return indexed

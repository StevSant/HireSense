from __future__ import annotations

import logging
from dataclasses import dataclass

from hiresense.ingestion.domain.embedding_text import job_text
from hiresense.ingestion.domain.job_list_criteria import JobListCriteria
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.ports.jobs_repository import JobsRepositoryPort
from hiresense.ports.embedding import EmbeddingPort
from hiresense.ports.vector_store import VectorStorePort

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
    ) -> None:
        self._boards_repo = boards_repo
        self._portals_repo = portals_repo
        self._embedding = embedding
        self._vector_store = vector_store

    async def run(self) -> BackfillResult:
        """Embed + upsert open jobs in both buckets. Returns per-bucket counts."""
        if self._vector_store is None:
            logger.warning("EmbeddingBackfillService: vector store not configured, skipping")
            return BackfillResult(boards=0, portals=0)

        # NOTE: single-batch embed; chunk if corpus grows large
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

        texts = [job_text(j) for j in jobs]
        try:
            vectors = await self._embedding.embed(texts)
        except Exception:
            logger.exception(
                "Backfill embedding batch failed (bucket=%s, size=%d)", bucket, len(jobs)
            )
            return 0

        indexed = 0
        for job, vec in zip(jobs, vectors):
            if not vec:
                continue
            try:
                await self._vector_store.upsert(
                    job.id,
                    vec,
                    {"bucket": bucket, "source": job.source},
                )
                indexed += 1
            except Exception:
                logger.exception("Backfill vector upsert failed for job %s", job.id)

        logger.info("Backfill indexed %d/%d jobs (bucket=%s)", indexed, len(jobs), bucket)
        return indexed

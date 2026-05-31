from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from hiresense.ingestion.domain.models import NormalizedJob

logger = logging.getLogger(__name__)

_JOB_TEXT_CHAR_LIMIT = 4000


class _RepositoryPort(Protocol):
    def list_all(self) -> list[NormalizedJob]: ...


def _job_text(job: NormalizedJob) -> str:
    parts = [job.title, " ".join(job.skills), job.description]
    return "\n".join(p for p in parts if p)[:_JOB_TEXT_CHAR_LIMIT]


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
        boards_repo: _RepositoryPort,
        portals_repo: _RepositoryPort,
        embedding: Any,
        vector_store: Any,
    ) -> None:
        self._boards_repo = boards_repo
        self._portals_repo = portals_repo
        self._embedding = embedding
        self._vector_store = vector_store

    async def run(self) -> BackfillResult:
        """Embed + upsert all jobs in both buckets. Returns per-bucket counts."""
        if self._vector_store is None:
            logger.warning("EmbeddingBackfillService: vector store not configured, skipping")
            return BackfillResult(boards=0, portals=0)

        boards_count = await self._backfill_bucket(
            self._boards_repo.list_all(), bucket="boards"
        )
        portals_count = await self._backfill_bucket(
            self._portals_repo.list_all(), bucket="portals"
        )
        return BackfillResult(boards=boards_count, portals=portals_count)

    async def _backfill_bucket(self, jobs: list[NormalizedJob], *, bucket: str) -> int:
        if not jobs:
            return 0

        texts = [_job_text(j) for j in jobs]
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

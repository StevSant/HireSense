"""Backfill pgvector embeddings for all stored ingested jobs.

Run once after applying migration 014 so semantic search isn't empty on first use:

    uv run python scripts/backfill_embeddings.py

Idempotent — re-running re-embeds and upserts (ON CONFLICT) every job. Logs how
many jobs were indexed vs skipped per bucket (no silent truncation).
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from hiresense.bootstrap.shared_infra import build_shared_infra
from hiresense.config import Settings
from hiresense.ingestion.domain import JobEmbeddingIndexer
from hiresense.ingestion.infrastructure import JobsRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_embeddings")


async def _run() -> None:
    settings = Settings()
    async with httpx.AsyncClient(timeout=settings.http_timeout) as http_client:
        infra = build_shared_infra(settings, http_client)
        if infra.vector_store is None:
            logger.error(
                "VECTOR_STORE_PROVIDER is not 'pgvector' (got %r) — nothing to backfill",
                settings.vector_store_provider,
            )
            return

        total_indexed = 0
        total_skipped = 0
        for bucket in ("boards", "portals"):
            repo = JobsRepository(session_factory=infra.sync_session_factory, bucket=bucket)
            jobs = repo.list_all()
            indexer = JobEmbeddingIndexer(infra.embedding, infra.vector_store, bucket=bucket)
            indexed = await indexer.index(jobs)
            skipped = len(jobs) - indexed
            total_indexed += indexed
            total_skipped += skipped
            logger.info(
                "bucket=%s: %d jobs, %d indexed, %d skipped",
                bucket,
                len(jobs),
                indexed,
                skipped,
            )
        logger.info(
            "backfill complete: %d indexed, %d skipped", total_indexed, total_skipped
        )


if __name__ == "__main__":
    asyncio.run(_run())

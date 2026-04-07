from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel

from hiresense.matching.domain.scorers.base import DimensionResult

logger = logging.getLogger(__name__)


class BatchResult(BaseModel):
    job_title: str
    company: str
    source: str
    source_id: str
    composite_score: float
    dimensions: list[DimensionResult]


class BatchEvaluationService:
    def __init__(self, orchestrator: Any, concurrency: int = 3) -> None:
        self._orchestrator = orchestrator
        self._semaphore = asyncio.Semaphore(concurrency)

    async def evaluate_batch(self, jobs: list[dict]) -> list[BatchResult]:
        if not jobs:
            return []

        async def evaluate_one(job: dict) -> BatchResult:
            async with self._semaphore:
                try:
                    result = await self._orchestrator.evaluate(job=job, profile=None)
                    return BatchResult(
                        job_title=result.job_title,
                        company=result.company,
                        source=job.get("source", "unknown"),
                        source_id=job.get("source_id", ""),
                        composite_score=result.composite_score,
                        dimensions=list(result.dimensions),
                    )
                except Exception as exc:
                    logger.warning("Batch evaluation failed for %s: %s", job.get("title", ""), exc)
                    return BatchResult(
                        job_title=job.get("title", "Unknown"),
                        company=job.get("company", "Unknown"),
                        source=job.get("source", "unknown"),
                        source_id=job.get("source_id", ""),
                        composite_score=0.5,
                        dimensions=[],
                    )

        results = await asyncio.gather(*[evaluate_one(j) for j in jobs])
        return sorted(results, key=lambda r: r.composite_score, reverse=True)

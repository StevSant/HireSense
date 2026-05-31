from __future__ import annotations

import asyncio
import logging
from typing import Any

from hiresense.ingestion.domain.closed_listing_classifier import Verdict, classify_listing

logger = logging.getLogger(__name__)


class JobRevalidationService:
    """Throttled URL-probe sweep that closes dead listings for feed/search sources.

    Disappearance detection (the orchestrator/scanner) covers snapshot sources;
    this covers the rest by re-fetching each open job's URL and closing it when
    the page is gone (404/410) or carries a "no longer available" marker. UNKNOWN
    results (5xx, timeouts) never close a job. Network cost is bounded by a
    per-run batch cap, a concurrency limit, and a per-request delay.
    """

    def __init__(
        self,
        *,
        http_client: Any,
        repository: Any,
        indexer: Any | None,
        sources: list[str],
        markers: list[str],
        batch: int,
        concurrency: int,
        delay: float,
    ) -> None:
        self._http = http_client
        self._repo = repository
        self._indexer = indexer
        self._sources = sources
        self._markers = markers
        self._batch = batch
        self._sem = asyncio.Semaphore(max(1, concurrency))
        self._delay = delay

    async def sweep(self) -> list[str]:
        jobs = self._repo.find_open_stale(self._sources, self._batch)
        if not jobs:
            return []
        verdicts = await asyncio.gather(*(self._probe(j) for j in jobs))
        to_close = [j.id for j, v in zip(jobs, verdicts) if v == Verdict.CLOSED]
        self._repo.mark_checked([j.id for j in jobs])
        if to_close:
            self._repo.mark_closed(to_close)
            if self._indexer is not None:
                await self._indexer.remove(to_close)
        logger.info(
            "Revalidation sweep: probed %d, closed %d", len(jobs), len(to_close)
        )
        return to_close

    async def _probe(self, job: Any) -> Verdict:
        async with self._sem:
            try:
                resp = await self._http.get(job.url, follow_redirects=True)
            except Exception:
                return Verdict.UNKNOWN
            finally:
                if self._delay:
                    await asyncio.sleep(self._delay)
            return classify_listing(
                status_code=resp.status_code,
                body=getattr(resp, "text", "") or "",
                markers=self._markers,
            )

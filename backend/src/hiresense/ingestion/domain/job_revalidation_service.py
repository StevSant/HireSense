from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
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

    Some sources don't expose closure on the public listing URL the user clicks:
    LinkedIn's `/jobs/view/<id>` returns a login wall server-side, but its guest
    API (`/jobs-guest/jobs/api/jobPosting/<id>`) returns 200 + "No longer
    accepting applications" when closed. `probe_url_builders` maps such sources
    to a function that derives the probe URL from the job (falling back to
    job.url for everything else).
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
        probe_url_builders: dict[str, Callable[[Any], str]] | None = None,
        user_agent: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._http = http_client
        self._repo = repository
        self._indexer = indexer
        self._sources = sources
        self._markers = markers
        self._probe_url_builders = probe_url_builders or {}
        # A browser-like header set: the shared client's default python-httpx UA
        # is 403'd by some listing hosts, which would mask a real closure signal
        # as UNKNOWN. Only sent when a UA is configured.
        self._probe_headers: dict[str, str] = (
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            if user_agent
            else {}
        )
        self._batch = batch
        self._sem = asyncio.Semaphore(max(1, concurrency))
        self._delay = delay
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Guards against overlapping sweeps (fetch + the manual button can both
        # trigger one); a second trigger while one runs is a no-op.
        self._sweeping = False

    def _probe_url(self, job: Any) -> str:
        """The URL to probe for closure — a per-source override or job.url."""
        builder = self._probe_url_builders.get(job.source)
        return builder(job) if builder else job.url

    async def sweep(self) -> list[str]:
        """Probe EVERY open job of the probeable sources and close the dead ones.

        Walks the whole corpus in `batch`-sized chunks (oldest-checked first),
        closing per chunk so closures surface incrementally rather than only
        when the full run finishes. Bounded by the concurrency limit + per-probe
        delay, so a large corpus takes minutes — callers run it in the
        background. Re-entrant triggers are skipped via the `_sweeping` guard.
        """
        if self._sweeping:
            logger.info("Revalidation sweep already in progress; skipping trigger")
            return []
        self._sweeping = True
        closed: list[str] = []
        checked: set[str] = set()
        try:
            # Expiry-based closure first: sources whose public pages block URL
            # probes (e.g. Himalayas) carry a source-declared expiry_date instead.
            # DB-side and cheap — no HTTP.
            closed.extend(await self._close_expired())
            while True:
                jobs = await asyncio.to_thread(
                    self._repo.find_open_stale, self._sources, self._batch
                )
                # find_open_stale re-orders by last_checked_at, which we stamp each
                # chunk — so successive calls advance through the corpus. Stop once
                # a chunk yields nothing new (every open job has been probed).
                jobs = [j for j in jobs if j.id not in checked]
                if not jobs:
                    break
                checked.update(j.id for j in jobs)
                closed.extend(await self._probe_and_close(jobs))
            logger.info(
                "Revalidation sweep complete: probed %d, closed %d",
                len(checked),
                len(closed),
            )
            return closed
        finally:
            self._sweeping = False

    async def _close_expired(self) -> list[str]:
        """Close open jobs past their source-declared expiry and evict them from
        the index. Returns the closed ids."""
        expired = await asyncio.to_thread(self._repo.close_expired, self._clock())
        if expired:
            if self._indexer is not None:
                await self._indexer.remove(expired)
            logger.info("Revalidation: closed %d expired listing(s)", len(expired))
        return expired

    async def revalidate_ids(self, job_ids: list[str]) -> list[str]:
        """Probe a specific set of jobs NOW and close the dead ones.

        Backs the immediate half of the "Check closed" action: the user passes
        the jobs currently on screen so they get probed and closed right away,
        independent of the paced full-corpus sweep (no `_sweeping` guard — this
        always runs). Ids that are missing, already closed, or from a
        non-probeable source (e.g. hn_hiring) are skipped.
        """
        if not job_ids:
            return []
        jobs = await asyncio.to_thread(self._collect_probeable, job_ids)
        return await self._probe_and_close(jobs)

    def _collect_probeable(self, job_ids: list[str]) -> list[Any]:
        jobs: list[Any] = []
        for job_id in job_ids:
            job = self._repo.get_by_id(job_id)
            if job is not None and job.status == "open" and job.source in self._sources:
                jobs.append(job)
        return jobs

    async def _probe_and_close(self, jobs: list[Any]) -> list[str]:
        if not jobs:
            return []
        verdicts = await asyncio.gather(*(self._probe(j) for j in jobs))
        to_close = [j.id for j, v in zip(jobs, verdicts) if v == Verdict.CLOSED]
        await asyncio.to_thread(self._repo.mark_checked, [j.id for j in jobs])
        if to_close:
            await asyncio.to_thread(self._repo.mark_closed, to_close)
            if self._indexer is not None:
                await self._indexer.remove(to_close)
        logger.info("Revalidation: probed %d, closed %d", len(jobs), len(to_close))
        return to_close

    async def _probe(self, job: Any) -> Verdict:
        probe_url = self._probe_url(job)
        async with self._sem:
            try:
                resp = await self._http.get(
                    probe_url, follow_redirects=True, headers=self._probe_headers
                )
            except Exception as exc:
                # Transient transport failures must never close a job, but a
                # silently swallowed probe makes sweeps undebuggable — log it.
                logger.warning("Revalidation probe failed for %s: %s", probe_url, exc)
                return Verdict.UNKNOWN
            finally:
                if self._delay:
                    await asyncio.sleep(self._delay)
            return classify_listing(
                status_code=resp.status_code,
                body=getattr(resp, "text", "") or "",
                markers=self._markers,
            )

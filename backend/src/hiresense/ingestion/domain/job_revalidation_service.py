from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from hiresense.ingestion.domain.closed_listing_classifier import (
    Verdict,
    classify_listing,
    closure_reason,
)
from hiresense.ingestion.domain.dead_end_redirect import is_dead_end_redirect
from hiresense.ingestion.domain.host_rate_limiter import HostRateLimiter
from hiresense.ingestion.domain.job_closure_reason import JobClosureReason
from hiresense.ingestion.domain.job_history_recorder import JobHistoryRecorder
from hiresense.ingestion.domain.ssrf_guard import is_safe_probe_url

logger = logging.getLogger(__name__)

# Status codes that carry a Location we follow — manually, re-validating each
# hop — so an allowlisted host can't bounce the probe to an internal target.
_REDIRECT_STATUS = frozenset({301, 302, 303, 307, 308})


class _DeadEndRedirect(Exception):
    """A probe was redirected to a generic landing page (site root, or a URL
    carrying a configured expired-listing marker). Signals CLOSED without
    spending a second request on the landing page itself."""


class _ProbeBlocked(Exception):
    """A probe target was refused by the SSRF guard or its redirect chain ran
    too long. Signals UNKNOWN to the caller — never a closure."""


class JobRevalidationService:
    """Throttled URL-probe sweep that closes dead listings for feed/search sources.

    Disappearance detection (the orchestrator/scanner) covers snapshot sources;
    this covers the rest by re-fetching each open job's URL and closing it when
    the page is gone (404/410) or carries a "no longer available" marker. UNKNOWN
    results (5xx, timeouts) never close a job. Network cost is bounded by a
    per-run batch cap, a global in-flight ceiling, and a per-host rate limit
    (minimum interval + in-flight cap per board).

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
        host_concurrency: int = 4,
        max_probe_bytes: int = 262144,
        max_redirects: int = 5,
        url_guard: Callable[[str], bool] | None = None,
        probe_url_builders: dict[str, Callable[[Any], str]] | None = None,
        user_agent: str | None = None,
        expired_redirect_markers: list[str] | None = None,
        clock: Callable[[], datetime] | None = None,
        history: JobHistoryRecorder | None = None,
    ) -> None:
        self._http = http_client
        self._repo = repository
        self._indexer = indexer
        self._history = history
        self._sources = sources
        self._markers = markers
        self._expired_redirect_markers = expired_redirect_markers or []
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
        # Two-level throttle. `_sem` is a whole-sweep ceiling on in-flight
        # requests; the real politeness budget is per-host and lives in the
        # limiter, so probes to different boards no longer queue behind each
        # other. A single global semaphore made a sweep run at
        # concurrency/(latency+delay) requests per second across ALL hosts.
        self._sem = asyncio.Semaphore(max(1, concurrency))
        self._limiter = HostRateLimiter(min_interval=delay, concurrency=host_concurrency)
        # SSRF hardening: cap the streamed body and the redirect chain, and
        # validate every hop's target. Guard is injectable so tests run offline.
        self._max_probe_bytes = max(1, max_probe_bytes)
        self._max_redirects = max(0, max_redirects)
        self._url_guard = url_guard or is_safe_probe_url
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Guards against overlapping sweeps (fetch + the manual button can both
        # trigger one); a second trigger while one runs is a no-op.
        self._sweeping = False
        # Sweep progress, read by GET /ingestion/revalidate/status. A full sweep
        # of a large corpus runs for tens of minutes; without this the UI can
        # only show an indefinite "still scanning" banner it can never clear.
        self._checked_count = 0
        self._total_count = 0
        self._closed_count = 0

    def _probe_url(self, job: Any) -> str:
        """The URL to probe for closure — a per-source override or job.url."""
        builder = self._probe_url_builders.get(job.source)
        return builder(job) if builder else job.url

    async def sweep(self) -> list[str]:
        """Probe EVERY open job of the probeable sources and close the dead ones.

        Walks the whole corpus in `batch`-sized chunks (oldest-checked first),
        closing per chunk so closures surface incrementally rather than only
        when the full run finishes. Bounded by the per-host rate limit and the
        global in-flight ceiling, so a large corpus still takes minutes —
        callers run it in the background. Re-entrant triggers are skipped via
        the `_sweeping` guard.
        """
        if self._sweeping:
            logger.info("Revalidation sweep already in progress; skipping trigger")
            return []
        self._sweeping = True
        closed: list[str] = []
        checked: set[str] = set()
        self._checked_count = 0
        self._closed_count = 0
        self._total_count = await asyncio.to_thread(self._repo.count_open, self._sources)
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
                self._closed_count = len(closed)
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
            if self._history is not None:
                await asyncio.to_thread(
                    self._history.record_closures, expired, JobClosureReason.EXPIRY
                )
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

    def progress(self) -> dict[str, Any]:
        """Snapshot of the current (or last) sweep, for the status endpoint.

        `total` is the open-job count captured when the sweep started, so the
        ratio is stable even as jobs close underneath it.
        """
        return {
            "sweeping": self._sweeping,
            "checked": self._checked_count,
            "total": self._total_count,
            "closed": self._closed_count,
        }

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
        results = await asyncio.gather(*(self._probe_counted(j) for j in jobs))
        by_reason: dict[JobClosureReason, list[str]] = {}
        to_close: list[str] = []
        for job, (verdict, reason) in zip(jobs, results):
            if verdict != Verdict.CLOSED:
                continue
            to_close.append(job.id)
            # reason is always set on a CLOSED verdict; the fallback keeps a
            # future classifier path from silently dropping the closure.
            by_reason.setdefault(reason or JobClosureReason.PROBE_404, []).append(job.id)
        await asyncio.to_thread(self._repo.mark_checked, [j.id for j in jobs])
        if to_close:
            await asyncio.to_thread(self._repo.mark_closed, to_close)
            if self._indexer is not None:
                await self._indexer.remove(to_close)
            if self._history is not None:
                for reason, ids in by_reason.items():
                    # run_id stays None: the sweep is not an ingestion run.
                    await asyncio.to_thread(self._history.record_closures, ids, reason)
        logger.info("Revalidation: probed %d, closed %d", len(jobs), len(to_close))
        return to_close

    async def _probe_counted(self, job: Any) -> tuple[Verdict, JobClosureReason | None]:
        """Probe one job and advance the progress counter as it resolves.

        Counting once per finished chunk instead left `checked` at 0 for the ~100
        seconds a 100-job chunk takes, so the UI opened on "0 of 1873" —
        reproducing the very "looks stuck" impression this progress exists to
        remove.
        """
        result = await self._probe(job)
        self._checked_count += 1
        return result

    async def _probe(self, job: Any) -> tuple[Verdict, JobClosureReason | None]:
        probe_url = self._probe_url(job)
        async with self._sem:
            try:
                status_code, body = await self._fetch_capped(probe_url)
            except _DeadEndRedirect as exc:
                # The board bounced a specific listing to a generic page, which
                # is how most of them signal removal. Closing here also stops the
                # job being re-probed on every future sweep.
                logger.info("Revalidation: dead-end redirect for %s (%s)", probe_url, exc)
                return Verdict.CLOSED, JobClosureReason.DEAD_END_REDIRECT
            except _ProbeBlocked as exc:
                # A refused (SSRF) or over-redirected target is not a closure
                # signal — treat as UNKNOWN so a crafted listing can neither
                # drive internal requests nor false-close a job.
                logger.warning("Revalidation probe blocked for %s: %s", probe_url, exc)
                return Verdict.UNKNOWN, None
            except Exception as exc:
                # Transient transport failures must never close a job, but a
                # silently swallowed probe makes sweeps undebuggable — log it.
                logger.warning("Revalidation probe failed for %s: %s", probe_url, exc)
                return Verdict.UNKNOWN, None
            verdict = classify_listing(
                status_code=status_code,
                body=body,
                markers=self._markers,
            )
            reason = closure_reason(status_code) if verdict == Verdict.CLOSED else None
            return verdict, reason

    async def _fetch_capped(self, url: str) -> tuple[int, str]:
        """Fetch ``url`` with an SSRF check on every hop and a capped body read.

        Redirects are followed manually (not by the HTTP client) so each hop's
        target is re-validated before we connect — an allowlisted host can no
        longer bounce the probe to an internal address. The body is streamed and
        truncated to ``max_probe_bytes`` so an adversarial page can't exhaust
        memory. Raises ``_ProbeBlocked`` on a disallowed target or a redirect
        chain longer than ``max_redirects``.
        """
        current = url
        for _ in range(self._max_redirects + 1):
            # DNS resolution inside the guard is blocking — offload it.
            if not await asyncio.to_thread(self._url_guard, current):
                raise _ProbeBlocked(f"target is not a public http(s) address: {current}")
            # Pace by the hop's own host: a redirect chain that lands on another
            # board must respect that board's interval, not the origin's.
            async with (
                self._limiter.slot(current),
                self._http.stream(
                    "GET", current, follow_redirects=False, headers=self._probe_headers
                ) as resp,
            ):
                location = resp.headers.get("location")
                if resp.status_code in _REDIRECT_STATUS and location:
                    target = urljoin(current, location)
                    if is_dead_end_redirect(url, target, self._expired_redirect_markers):
                        raise _DeadEndRedirect(f"{url} -> {target}")
                    current = target
                    continue
                body = await self._read_capped(resp)
                return resp.status_code, body
        raise _ProbeBlocked(f"exceeded {self._max_redirects} redirects from {url}")

    async def _read_capped(self, resp: Any) -> str:
        """Read at most ``max_probe_bytes`` of the streamed response body."""
        chunks: list[bytes] = []
        total = 0
        async for chunk in resp.aiter_bytes():
            chunks.append(chunk)
            total += len(chunk)
            if total >= self._max_probe_bytes:
                break
        raw = b"".join(chunks)[: self._max_probe_bytes]
        encoding = getattr(resp, "encoding", None) or "utf-8"
        return raw.decode(encoding, errors="replace")

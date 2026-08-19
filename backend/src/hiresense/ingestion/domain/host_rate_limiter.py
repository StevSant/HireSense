from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from urllib.parse import urlsplit


class HostRateLimiter:
    """Paces outbound requests per target host instead of globally.

    A single global semaphore + per-request sleep throttles every host behind
    one queue: probing getonbrd waits on a remoteok request that shares no
    infrastructure with it. The politeness budget that motivates the throttle is
    per-host, so this keys it that way — each host gets its own minimum interval
    between requests and its own in-flight cap, and unrelated hosts proceed in
    parallel.

    ``min_interval`` is enforced by reserving a host's next slot at claim time
    (before sleeping), so N callers piling onto one host queue up at
    ``min_interval`` apart rather than all waking at the same instant.
    """

    def __init__(
        self,
        *,
        min_interval: float,
        concurrency: int,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._min_interval = max(0.0, min_interval)
        self._concurrency = max(1, concurrency)
        # Clock and sleeper are injectable so pacing can be asserted exactly in
        # tests without patching asyncio (which would also silence the test's
        # own yields) and without wall-clock tolerance.
        self._clock = clock
        self._sleeper = sleeper or asyncio.sleep
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._next_allowed: dict[str, float] = {}

    @asynccontextmanager
    async def slot(self, url: str) -> AsyncIterator[None]:
        """Hold a slot for ``url``'s host for the duration of the block."""
        host = urlsplit(url).netloc.lower()
        semaphore = self._semaphores.get(host)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self._concurrency)
            self._semaphores[host] = semaphore
        async with semaphore:
            await self._wait_turn(host)
            yield

    def _now(self) -> float:
        if self._clock is not None:
            return self._clock()
        return asyncio.get_running_loop().time()

    async def _wait_turn(self, host: str) -> None:
        if not self._min_interval:
            return
        now = self._now()
        earliest = self._next_allowed.get(host, 0.0)
        # Reserve before sleeping: concurrent claimants on the same host each
        # take a distinct future slot rather than racing on a stale timestamp.
        self._next_allowed[host] = max(now, earliest) + self._min_interval
        wait = earliest - now
        if wait > 0:
            await self._sleeper(wait)

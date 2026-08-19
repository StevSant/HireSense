from __future__ import annotations

import asyncio

import pytest

from hiresense.ingestion.domain import HostRateLimiter


class _Recorder:
    """Captures the limiter's waits and advances a fake clock by each one, so
    pacing is asserted exactly instead of by wall-clock tolerance."""

    def __init__(self, *, advance: bool = True) -> None:
        self.waits: list[float] = []
        self.now = 0.0
        self._advance = advance

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        if self._advance:
            self.now += seconds


@pytest.mark.asyncio
async def test_same_host_requests_are_spaced_by_min_interval() -> None:
    rec = _Recorder()
    limiter = HostRateLimiter(min_interval=1.0, concurrency=4, clock=rec.clock, sleeper=rec.sleep)

    for _ in range(3):
        async with limiter.slot("https://board.example/jobs/1"):
            pass

    # The first claim is free; each later one waits out the interval its
    # predecessor reserved.
    assert rec.waits == [1.0, 1.0]


@pytest.mark.asyncio
async def test_different_hosts_do_not_wait_on_each_other() -> None:
    rec = _Recorder()
    limiter = HostRateLimiter(min_interval=1.0, concurrency=4, clock=rec.clock, sleeper=rec.sleep)

    for host in ("a.example", "b.example", "c.example"):
        async with limiter.slot(f"https://{host}/jobs/1"):
            pass

    assert rec.waits == []


@pytest.mark.asyncio
async def test_concurrent_claims_on_one_host_take_distinct_slots() -> None:
    """Reserving a slot before sleeping is what stops N waiters waking together."""
    rec = _Recorder(advance=False)
    limiter = HostRateLimiter(min_interval=1.0, concurrency=4, clock=rec.clock, sleeper=rec.sleep)

    async def _claim() -> None:
        async with limiter.slot("https://board.example/x"):
            pass

    await asyncio.gather(*(_claim() for _ in range(4)))

    assert rec.waits == [1.0, 2.0, 3.0]


@pytest.mark.asyncio
async def test_host_concurrency_caps_simultaneous_requests_per_host() -> None:
    rec = _Recorder()
    limiter = HostRateLimiter(min_interval=0.0, concurrency=2, clock=rec.clock, sleeper=rec.sleep)
    in_flight = 0
    peak = 0
    release = asyncio.Event()

    async def _claim() -> None:
        nonlocal in_flight, peak
        async with limiter.slot("https://board.example/x"):
            in_flight += 1
            peak = max(peak, in_flight)
            await release.wait()
            in_flight -= 1

    task = asyncio.gather(*(_claim() for _ in range(5)))
    await asyncio.sleep(0)
    release.set()
    await task

    assert peak == 2


@pytest.mark.asyncio
async def test_zero_interval_never_sleeps() -> None:
    rec = _Recorder()
    limiter = HostRateLimiter(min_interval=0.0, concurrency=2, clock=rec.clock, sleeper=rec.sleep)

    for _ in range(3):
        async with limiter.slot("https://board.example/x"):
            pass

    assert rec.waits == []

from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowRateLimiter:
    """Thread-safe in-process sliding-window rate limiter.

    Counts are per limiter instance (single-process deployment) and reset on
    restart — deliberate for a self-hosted single-user app; no external store.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        # Timestamp of the last idle-key sweep. Seeded at construction so the
        # first sweep only fires after a full window has elapsed.
        self._last_sweep = time.monotonic()

    @property
    def window_seconds(self) -> float:
        return self._window

    def allow(self, key: str) -> bool:
        """Record one request for `key`; False when the window is exhausted."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            self._sweep_idle_keys(now, cutoff)
            events = self._events.get(key)
            if events is None:
                events = self._events[key] = deque()
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self._max:
                return False
            events.append(now)
            return True

    def _sweep_idle_keys(self, now: float, cutoff: float) -> None:
        """Drop keys whose most recent request predates the window.

        Without this the map grows unbounded over a long-lived process facing
        many distinct client IPs: idle keys are never revisited, so their
        deques are never pruned and the keys leak. Throttled to once per window
        so the O(keys) walk stays amortized-cheap, and gated on the newest
        timestamp so a still-active key (with only some stale entries) is kept.
        """
        if now - self._last_sweep < self._window:
            return
        self._last_sweep = now
        stale = [key for key, events in self._events.items() if not events or events[-1] < cutoff]
        for key in stale:
            del self._events[key]

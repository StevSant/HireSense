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

    @property
    def window_seconds(self) -> float:
        return self._window

    def allow(self, key: str) -> bool:
        """Record one request for `key`; False when the window is exhausted."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self._max:
                return False
            events.append(now)
            return True

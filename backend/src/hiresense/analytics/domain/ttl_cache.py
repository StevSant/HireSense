from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class TtlCache:
    """Tiny per-key time-based cache. `clock` is injectable for testing."""

    def __init__(self, *, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._store: dict[str, tuple[float, Any]] = {}

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> Any:
        now = self._clock()
        hit = self._store.get(key)
        if hit is not None and (now - hit[0]) < self._ttl:
            return hit[1]
        value = compute()
        self._store[key] = (now, value)
        return value

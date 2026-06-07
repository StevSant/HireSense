from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Transport-level httpx errors that are safe to retry: timeouts, connection
# resets, DNS/connect failures, etc. (everything under TransportError).
_RETRYABLE_EXCEPTIONS = (httpx.TransportError,)


class RetryingAsyncClient:
    """Drop-in wrapper around ``httpx.AsyncClient`` adding retry + backoff.

    Wraps the verbs the ingestion adapters use (``get``/``post``/``request``)
    so a single transient failure no longer aborts an entire source fetch.
    Retries on transport errors (timeouts, connection resets) and on a
    configurable set of HTTP status codes (default 429/5xx), with exponential
    backoff capped at ``max_retries`` attempts.

    The wrapper is intentionally a thin facade: any attribute it does not
    override (``aclose``, ``stream``, headers, …) is delegated to the wrapped
    client, so it is interchangeable with the real ``httpx.AsyncClient`` for
    every consumer.

    The sleep callable is injectable so tests can assert backoff delays
    without actually sleeping.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        max_retries: int,
        base_delay: float,
        retry_status_codes: Sequence[int],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._retry_status_codes = frozenset(retry_status_codes)
        self._sleep = sleep

    @property
    def wrapped(self) -> httpx.AsyncClient:
        """The underlying httpx client (escape hatch for advanced callers)."""
        return self._client

    async def get(self, url: Any, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: Any, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def request(self, method: str, url: Any, **kwargs: Any) -> httpx.Response:
        # Total attempts = 1 initial + max_retries retries.
        last_exc: BaseException | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(method, url, **kwargs)
            except _RETRYABLE_EXCEPTIONS as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    raise
                await self._backoff(attempt, method, url, reason=type(exc).__name__)
                continue

            if (
                response.status_code in self._retry_status_codes
                and attempt < self._max_retries
            ):
                await self._backoff(
                    attempt, method, url, reason=f"HTTP {response.status_code}"
                )
                continue

            return response

        # Only reachable if the loop exhausted on an exception path without
        # returning; re-raise the last captured transport error defensively.
        if last_exc is not None:  # pragma: no cover - defensive
            raise last_exc
        raise RuntimeError("retry loop exited without a response")  # pragma: no cover

    async def _backoff(self, attempt: int, method: str, url: Any, *, reason: str) -> None:
        delay = self._base_delay * (2**attempt)
        logger.warning(
            "Retrying %s %s after %s (attempt %d/%d), sleeping %.2fs",
            method,
            url,
            reason,
            attempt + 1,
            self._max_retries,
            delay,
        )
        await self._sleep(delay)

    def __getattr__(self, name: str) -> Any:
        # Delegate any non-overridden attribute (aclose, stream, headers,
        # is_closed, …) to the wrapped client so this stays a true drop-in.
        return getattr(self._client, name)

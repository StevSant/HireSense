from __future__ import annotations

import httpx
import pytest

from hiresense.adapters.http import RetryingAsyncClient


class _FakeClient:
    """Stand-in for httpx.AsyncClient with a scripted sequence of outcomes.

    Each entry in ``outcomes`` is either an int status code (a Response is
    returned) or an Exception instance (raised). One outcome is consumed per
    ``request`` call.
    """

    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[tuple[str, object, dict]] = []

    async def request(self, method: str, url: object, **kwargs: object) -> httpx.Response:
        self.calls.append((method, url, kwargs))
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(status_code=int(outcome), request=httpx.Request(method, url))


class _FakeSleep:
    """Records the delays passed to it instead of actually sleeping."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def _make_client(client: _FakeClient, sleep: _FakeSleep, *, max_retries: int = 3):
    return RetryingAsyncClient(
        client,  # type: ignore[arg-type]
        max_retries=max_retries,
        base_delay=0.5,
        retry_status_codes=[429, 500, 502, 503, 504],
        sleep=sleep,
    )


@pytest.mark.asyncio
async def test_retries_retryable_status_then_succeeds() -> None:
    fake = _FakeClient([503, 200])
    sleep = _FakeSleep()
    wrapper = _make_client(fake, sleep)

    response = await wrapper.get("https://example.com")

    assert response.status_code == 200
    assert len(fake.calls) == 2
    assert sleep.delays == [0.5]  # one backoff before the successful retry


@pytest.mark.asyncio
async def test_retries_transport_error_then_succeeds() -> None:
    fake = _FakeClient([httpx.ConnectError("boom"), 200])
    sleep = _FakeSleep()
    wrapper = _make_client(fake, sleep)

    response = await wrapper.get("https://example.com")

    assert response.status_code == 200
    assert len(fake.calls) == 2
    assert sleep.delays == [0.5]


@pytest.mark.asyncio
async def test_gives_up_after_max_retries_on_status() -> None:
    # Always returns a retryable status: 1 initial + max_retries attempts.
    fake = _FakeClient([500, 500, 500, 500])
    sleep = _FakeSleep()
    wrapper = _make_client(fake, sleep, max_retries=3)

    response = await wrapper.get("https://example.com")

    # The last (still-failing) response is returned for raise_for_status() to act on.
    assert response.status_code == 500
    assert len(fake.calls) == 4  # initial + 3 retries
    assert len(sleep.delays) == 3  # one backoff per retry


@pytest.mark.asyncio
async def test_gives_up_after_max_retries_on_transport_error() -> None:
    err = httpx.ReadTimeout("slow")
    fake = _FakeClient([err, err, err, err])
    sleep = _FakeSleep()
    wrapper = _make_client(fake, sleep, max_retries=3)

    with pytest.raises(httpx.ReadTimeout):
        await wrapper.get("https://example.com")

    assert len(fake.calls) == 4  # initial + 3 retries
    assert len(sleep.delays) == 3


@pytest.mark.asyncio
async def test_backoff_is_exponential() -> None:
    fake = _FakeClient([500, 500, 500, 200])
    sleep = _FakeSleep()
    wrapper = _make_client(fake, sleep, max_retries=3)

    response = await wrapper.get("https://example.com")

    assert response.status_code == 200
    # base_delay=0.5 → 0.5 * 2**0, 0.5 * 2**1, 0.5 * 2**2
    assert sleep.delays == [0.5, 1.0, 2.0]


@pytest.mark.asyncio
async def test_post_is_wrapped_and_passes_kwargs() -> None:
    fake = _FakeClient([200])
    sleep = _FakeSleep()
    wrapper = _make_client(fake, sleep)

    await wrapper.post("https://example.com", params={"mode": "json"}, timeout=5.0)

    method, url, kwargs = fake.calls[0]
    assert method == "POST"
    assert url == "https://example.com"
    assert kwargs == {"params": {"mode": "json"}, "timeout": 5.0}


@pytest.mark.asyncio
async def test_non_retryable_status_returned_immediately() -> None:
    fake = _FakeClient([404])
    sleep = _FakeSleep()
    wrapper = _make_client(fake, sleep)

    response = await wrapper.get("https://example.com")

    assert response.status_code == 404
    assert len(fake.calls) == 1
    assert sleep.delays == []


@pytest.mark.asyncio
async def test_zero_max_retries_does_not_retry() -> None:
    fake = _FakeClient([503])
    sleep = _FakeSleep()
    wrapper = _make_client(fake, sleep, max_retries=0)

    response = await wrapper.get("https://example.com")

    assert response.status_code == 503
    assert len(fake.calls) == 1
    assert sleep.delays == []


def test_delegates_unknown_attributes_to_wrapped_client() -> None:
    fake = _FakeClient([])
    sleep = _FakeSleep()
    wrapper = _make_client(fake, sleep)

    # `calls` is not overridden on the wrapper → resolved on the wrapped client.
    assert wrapper.calls is fake.calls
    assert wrapper.wrapped is fake

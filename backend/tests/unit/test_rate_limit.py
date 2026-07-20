import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import enforce_expensive_rate_limit
from hiresense.kernel import SlidingWindowRateLimiter


def test_allows_up_to_max_requests() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60.0)
    assert all(limiter.allow("client") for _ in range(3))
    assert limiter.allow("client") is False


def test_keys_are_independent() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    assert limiter.allow("b") is True


def test_window_expiry_frees_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 1000.0}
    monkeypatch.setattr("hiresense.kernel.rate_limit.time.monotonic", lambda: clock["now"])
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=10.0)
    assert limiter.allow("client") is True
    assert limiter.allow("client") is False
    clock["now"] += 11.0
    assert limiter.allow("client") is True


def test_idle_keys_are_evicted_after_a_window(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 1000.0}
    monkeypatch.setattr("hiresense.kernel.rate_limit.time.monotonic", lambda: clock["now"])
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10.0)
    for ip in ("a", "b", "c"):
        assert limiter.allow(ip) is True
    assert len(limiter._events) == 3
    # After a full window elapses, the next call sweeps the now-idle keys so the
    # map shrinks instead of leaking one deque per distinct IP forever.
    clock["now"] += 11.0
    assert limiter.allow("d") is True
    assert set(limiter._events) == {"d"}


def test_sweep_keeps_still_active_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 1000.0}
    monkeypatch.setattr("hiresense.kernel.rate_limit.time.monotonic", lambda: clock["now"])
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10.0)
    assert limiter.allow("idle") is True
    clock["now"] += 6.0
    assert limiter.allow("active") is True  # recent, must survive the next sweep
    clock["now"] += 5.0  # 'idle' is now >window old; 'active' is only 5s old
    assert limiter.allow("trigger") is True  # crosses the sweep threshold
    assert "idle" not in limiter._events
    assert "active" in limiter._events


def _app_with_limiter(limiter: SlidingWindowRateLimiter | None) -> FastAPI:
    app = FastAPI()
    app.state.rate_limiter = limiter

    @app.get("/expensive", dependencies=[Depends(enforce_expensive_rate_limit)])
    async def expensive() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_dependency_returns_429_when_exhausted() -> None:
    app = _app_with_limiter(SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get("/expensive")
        second = await client.get("/expensive")
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "60"


@pytest.mark.asyncio
async def test_dependency_noops_without_limiter() -> None:
    app = _app_with_limiter(None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(5):
            resp = await client.get("/expensive")
            assert resp.status_code == 200

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api import router as identity_router
from hiresense.identity.api.provider import IdentityProvider
from hiresense.kernel import SlidingWindowRateLimiter

_USERNAME = "admin"
_PASSWORD = "secret"


def _build_app(
    *,
    login_limiter: SlidingWindowRateLimiter | None,
    generic_limiter: SlidingWindowRateLimiter | None,
) -> FastAPI:
    app = FastAPI()
    app.state.identity = IdentityProvider(
        username=_USERNAME, password=_PASSWORD, jwt_secret="test-secret"
    )
    app.state.settings = SimpleNamespace(
        session_cookie_name="hs_session",
        session_cookie_secure=False,
        session_cookie_samesite="strict",
        jwt_expiry_hours=24,
    )
    app.state.login_rate_limiter = login_limiter
    app.state.rate_limiter = generic_limiter
    app.include_router(identity_router)
    return app


@pytest.mark.asyncio
async def test_login_locks_out_before_the_generic_bucket_is_touched() -> None:
    # Login limiter far stricter than the shared expensive/generic bucket.
    login_limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=900.0)
    generic_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60.0)
    app = _build_app(login_limiter=login_limiter, generic_limiter=generic_limiter)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Wrong password so login stays 401 while the dedicated limiter fills up.
        for _ in range(3):
            resp = await c.post("/auth/login", json={"username": _USERNAME, "password": "wrong"})
            assert resp.status_code == 401
        # The 4th attempt trips the dedicated login limiter — well below the
        # 30-request generic bucket, which the login path never consumes.
        locked = await c.post("/auth/login", json={"username": _USERNAME, "password": "wrong"})
        assert locked.status_code == 429
        assert "Retry-After" in locked.headers

    # The generic bucket counted none of the login traffic: still fully available.
    assert generic_limiter.allow("t") is True
    assert len(generic_limiter._events["t"]) == 1


@pytest.mark.asyncio
async def test_login_not_limited_when_login_limiter_absent() -> None:
    # Bare app (no login limiter wired) must not 429 — enforcement is a no-op.
    app = _build_app(login_limiter=None, generic_limiter=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        for _ in range(6):
            resp = await c.post("/auth/login", json={"username": _USERNAME, "password": _PASSWORD})
            assert resp.status_code == 200

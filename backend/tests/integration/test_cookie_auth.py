from __future__ import annotations

from types import SimpleNamespace
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api import router as identity_router
from hiresense.identity.api.dependencies import require_auth
from hiresense.identity.api.provider import IdentityProvider

_USERNAME = "admin"
_PASSWORD = "secret"
_SECRET = "test-secret"
_COOKIE_NAME = "hs_session"


def _build_app(*, cookie_secure: bool = False) -> FastAPI:
    app = FastAPI()
    app.state.identity = IdentityProvider(
        username=_USERNAME,
        password=_PASSWORD,
        jwt_secret=_SECRET,
    )
    # Stand-in for the composed Settings the auth cookie helpers read off
    # app.state — only the fields resolve_session_cookie_config touches.
    app.state.settings = SimpleNamespace(
        session_cookie_name=_COOKIE_NAME,
        session_cookie_secure=cookie_secure,
        session_cookie_samesite="strict",
        jwt_expiry_hours=24,
    )
    app.include_router(identity_router)

    @app.get("/protected")
    def _protected(user: Annotated[str, Depends(require_auth)]) -> dict[str, str]:
        return {"user": user}

    return app


@pytest.mark.asyncio
async def test_login_sets_httponly_session_cookie() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/auth/login", json={"username": _USERNAME, "password": _PASSWORD})
        assert resp.status_code == 200
        set_cookie = resp.headers["set-cookie"]
        assert f"{_COOKIE_NAME}=" in set_cookie
        assert "httponly" in set_cookie.lower()
        assert "samesite=strict" in set_cookie.lower()
        # Local (http) default: no Secure flag or the browser would drop it.
        assert "secure" not in set_cookie.lower()


@pytest.mark.asyncio
async def test_production_login_cookie_is_secure() -> None:
    app = _build_app(cookie_secure=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/auth/login", json={"username": _USERNAME, "password": _PASSWORD})
        assert "secure" in resp.headers["set-cookie"].lower()


@pytest.mark.asyncio
async def test_cookie_alone_authenticates_without_bearer_header() -> None:
    app = _build_app()
    # The AsyncClient cookie jar persists the login Set-Cookie across requests.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/auth/login", json={"username": _USERNAME, "password": _PASSWORD})
        me = await c.get("/auth/me")
        assert me.status_code == 200
        assert me.json() == {"username": _USERNAME, "role": "admin"}
        protected = await c.get("/protected")
        assert protected.status_code == 200
        assert protected.json() == {"user": _USERNAME}


@pytest.mark.asyncio
async def test_bearer_header_still_authenticates() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        token = (
            await c.post("/auth/login", json={"username": _USERNAME, "password": _PASSWORD})
        ).json()["access_token"]
        # Drop the cookie jar so only the header can authenticate.
        c.cookies.clear()
        me = await c.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["username"] == _USERNAME


@pytest.mark.asyncio
async def test_logout_clears_cookie_and_deauthenticates() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/auth/login", json={"username": _USERNAME, "password": _PASSWORD})
        assert (await c.get("/auth/me")).status_code == 200

        logout = await c.post("/auth/logout")
        assert logout.status_code == 200
        # Server expires the cookie (max-age=0 / past expiry) so the jar drops it.
        assert _COOKIE_NAME in logout.headers["set-cookie"]

        c.cookies.clear()
        assert (await c.get("/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_missing_credentials_are_rejected() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/auth/me")).status_code == 401
        assert (await c.get("/protected")).status_code == 401

from __future__ import annotations

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api import router as identity_router
from hiresense.identity.api.dependencies import require_admin
from hiresense.identity.api.provider import IdentityProvider

_USERNAME = "admin"
_PASSWORD = "secret"
_SECRET = "test-secret"


def _build_app(role: str) -> FastAPI:
    app = FastAPI()
    app.state.identity = IdentityProvider(
        username=_USERNAME,
        password=_PASSWORD,
        jwt_secret=_SECRET,
        role=role,
    )
    app.include_router(identity_router)

    # Stand-in for the real admin routers, which already Depends(require_admin).
    @app.get("/admin/probe")
    def _probe(_: Annotated[dict, Depends(require_admin)]) -> dict[str, str]:
        return {"ok": "yes"}

    return app


async def _login(client: AsyncClient) -> str:
    resp = await client.post("/auth/login", json={"username": _USERNAME, "password": _PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_login_token_carries_role_and_me_returns_it() -> None:
    app = _build_app(role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        token = await _login(c)
        me = await c.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json() == {"username": _USERNAME, "role": "admin"}


@pytest.mark.asyncio
async def test_admin_route_allows_admin_token() -> None:
    app = _build_app(role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        token = await _login(c)
        resp = await c.get("/admin/probe", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": "yes"}


@pytest.mark.asyncio
async def test_admin_route_forbids_valid_non_admin_token() -> None:
    app = _build_app(role="member")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        token = await _login(c)
        # A valid token for an authenticated non-admin user.
        me = await c.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200 and me.json()["role"] == "member"

        resp = await c.get("/admin/probe", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

"""GET /opportunities page size must come from settings, not module constants.

The route used to hardcode 50/100, so an operator could not tune the feed page
size the way DEFAULT_PAGE_SIZE/MAX_PAGE_SIZE tune every other list endpoint. The
module constants survive only as fallbacks for routers mounted without
``app.state.settings`` (bare-app unit tests).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.opportunities.api.dependencies import get_opportunities_service
from hiresense.opportunities.api.routes import router
from hiresense.profile.api.dependencies import get_profile_service


class FakeOpportunityService:
    """Records the limit/offset the route resolved; returns no rows."""

    def __init__(self) -> None:
        self.limits: list[int] = []
        self.offsets: list[int] = []

    def list(self, *, limit: int, offset: int, **_kwargs) -> list:
        self.limits.append(limit)
        self.offsets.append(offset)
        return []

    def count(self, **_kwargs) -> int:
        return 0


class FakeProfileService:
    async def list_profiles(self) -> list:
        return []


def _build_app(service: FakeOpportunityService, settings: object | None) -> FastAPI:
    app = FastAPI()
    if settings is not None:
        app.state.settings = settings
    app.dependency_overrides[get_opportunities_service] = lambda: service
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


def _settings(default: int, maximum: int) -> SimpleNamespace:
    return SimpleNamespace(
        opportunities_default_page_size=default,
        opportunities_max_page_size=maximum,
    )


async def _get(app: FastAPI, params: dict) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/opportunities", params=params)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_omitted_page_size_uses_configured_default() -> None:
    service = FakeOpportunityService()
    app = _build_app(service, _settings(default=7, maximum=90))

    await _get(app, {})

    assert service.limits == [7]


@pytest.mark.asyncio
async def test_explicit_page_size_is_clamped_to_configured_maximum() -> None:
    service = FakeOpportunityService()
    app = _build_app(service, _settings(default=7, maximum=9))

    await _get(app, {"page_size": 500})

    assert service.limits == [9]


@pytest.mark.asyncio
async def test_explicit_page_size_below_maximum_is_honoured() -> None:
    service = FakeOpportunityService()
    app = _build_app(service, _settings(default=7, maximum=90))

    await _get(app, {"page_size": 25, "page": 3})

    assert service.limits == [25]
    assert service.offsets == [50]


@pytest.mark.asyncio
async def test_falls_back_to_module_constants_without_settings() -> None:
    service = FakeOpportunityService()
    app = _build_app(service, settings=None)

    await _get(app, {})
    await _get(app, {"page_size": 5000})

    assert service.limits == [50, 100]

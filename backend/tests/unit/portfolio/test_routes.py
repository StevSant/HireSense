from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.portfolio.api import router
from hiresense.portfolio.api.dependencies import get_projects_repository, get_sync_service
from hiresense.portfolio.domain import PortfolioProject, ProjectText, SyncResult


def _project(key: str) -> PortfolioProject:
    return PortfolioProject(
        id=key, source="supabase", source_key=key,
        translations={"en": ProjectText(title=key)},
    )


class _FakeSync:
    def __init__(self, result: SyncResult):
        self._result = result

    async def sync(self) -> SyncResult:
        return self._result


class _FakeRepo:
    def __init__(self, projects, last):
        self._projects, self._last = projects, last

    def list_all(self):
        return self._projects

    def last_synced_at(self):
        return self._last


def _app(sync=None, repo=None) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_sync_service] = lambda: sync
    app.dependency_overrides[get_projects_repository] = lambda: repo
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_requires_auth_without_token() -> None:
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.get("/portfolio/projects")).status_code == 401


@pytest.mark.asyncio
async def test_sync_503_when_unconfigured() -> None:
    app = _app(sync=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.post("/portfolio/sync")).status_code == 503


@pytest.mark.asyncio
async def test_sync_returns_result() -> None:
    result = SyncResult(
        counts_by_source={"supabase": 3}, errors={}, synced_at=datetime.now(timezone.utc)
    )
    app = _app(sync=_FakeSync(result))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post("/portfolio/sync")
    assert resp.status_code == 200
    assert resp.json()["counts_by_source"] == {"supabase": 3}


@pytest.mark.asyncio
async def test_sync_502_when_all_sources_fail() -> None:
    result = SyncResult(
        counts_by_source={}, errors={"supabase": "boom"}, synced_at=datetime.now(timezone.utc)
    )
    app = _app(sync=_FakeSync(result))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.post("/portfolio/sync")).status_code == 502


@pytest.mark.asyncio
async def test_list_projects_with_and_without_repo() -> None:
    last = datetime.now(timezone.utc)
    app = _app(repo=_FakeRepo([_project("a")], last))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        body = (await client.get("/portfolio/projects")).json()
    assert [p["source_key"] for p in body["projects"]] == ["a"]
    assert body["last_synced_at"] is not None

    app = _app(repo=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        body = (await client.get("/portfolio/projects")).json()
    assert body == {"projects": [], "last_synced_at": None}

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.ingestion.api.routes import get_portal_scanner, get_portals_config, router
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.domain.portal_scanner import ScanError, ScanFilters, ScanResult

_SAMPLE_JOB = NormalizedJob(
    id="scan-1",
    title="Backend Engineer",
    company="Acme",
    description="Build things",
    skills=["python", "fastapi"],
    location="Remote",
    source="greenhouse",
    source_type="api",
    language="en",
    url="https://boards.greenhouse.io/acme/jobs/1",
)

_SAMPLE_PORTALS_CONFIG = PortalsConfig(
    portals=[
        PortalEntry(
            name="Acme",
            platform="greenhouse",
            board_id="acme",
            categories=["engineering"],
        ),
        PortalEntry(
            name="Beta Corp",
            platform="lever",
            board_id="betacorp",
            categories=["product"],
        ),
    ]
)


class FakePortalScanner:
    def __init__(self, result: ScanResult) -> None:
        self._result = result
        self.last_filters: ScanFilters | None = None

    async def scan(self, filters: ScanFilters) -> ScanResult:
        self.last_filters = filters
        return self._result


def _make_app(scanner: FakePortalScanner, config: PortalsConfig = _SAMPLE_PORTALS_CONFIG) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_portal_scanner] = lambda: scanner
    app.dependency_overrides[get_portals_config] = lambda: config
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_scan_portals_returns_results() -> None:
    result = ScanResult(
        total_fetched=1,
        new=1,
        duplicates=0,
        jobs=[_SAMPLE_JOB],
        errors=[],
    )
    fake = FakePortalScanner(result)
    app = _make_app(fake)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/scan-portals", json={})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_fetched"] == 1
    assert data["new"] == 1
    assert data["duplicates"] == 0
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["title"] == "Backend Engineer"
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_scan_portals_passes_filters() -> None:
    result = ScanResult(total_fetched=0, new=0, duplicates=0, jobs=[], errors=[])
    fake = FakePortalScanner(result)
    app = _make_app(fake)

    payload = {
        "categories": ["engineering"],
        "companies": ["Acme"],
        "keyword": "python",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/scan-portals", json=payload)

    assert resp.status_code == 200
    assert fake.last_filters is not None
    assert fake.last_filters.categories == ["engineering"]
    assert fake.last_filters.companies == ["Acme"]
    assert fake.last_filters.keyword == "python"


@pytest.mark.asyncio
async def test_scan_portals_returns_errors() -> None:
    error = ScanError(portal="Acme", platform="greenhouse", error="Connection timeout")
    result = ScanResult(total_fetched=0, new=0, duplicates=0, jobs=[], errors=[error])
    fake = FakePortalScanner(result)
    app = _make_app(fake)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/scan-portals", json={})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["errors"]) == 1
    assert data["errors"][0]["portal"] == "Acme"
    assert data["errors"][0]["platform"] == "greenhouse"
    assert data["errors"][0]["error"] == "Connection timeout"


@pytest.mark.asyncio
async def test_get_portals_config() -> None:
    result = ScanResult(total_fetched=0, new=0, duplicates=0, jobs=[], errors=[])
    fake = FakePortalScanner(result)
    app = _make_app(fake)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/portals")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    names = {p["name"] for p in data}
    assert names == {"Acme", "Beta Corp"}
    assert data[0]["platform"] in {"greenhouse", "lever"}

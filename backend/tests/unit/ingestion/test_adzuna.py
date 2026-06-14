from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from hiresense.ingestion.adapters import AdzunaAdapter
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import AdzunaNormalizer
from hiresense.kernel.value_objects import SourceType

BASE_URL = "https://api.adzuna.com/v1/api/jobs"


class FakeResponse:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.status_code = 200

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        pass


class FakeHttpClient:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.urls: list[str] = []
        self.last_params: dict | None = None

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.urls.append(url)
        self.last_params = kwargs.get("params")
        return FakeResponse(self._data)


SAMPLE_JOB = {
    "id": "job1",
    "title": "Backend Developer",
    "description": "<p>Build services</p>",
    "company": {"display_name": "Acme MX"},
    "location": {"display_name": "Ciudad de México, MX", "area": ["Mexico", "CDMX"]},
    "salary_min": 50000,
    "salary_max": 70000,
    "category": {"label": "IT Jobs", "tag": "it-jobs"},
    "created": "2026-03-01T12:00:00Z",
    "redirect_url": "https://www.adzuna.com.mx/jobs/details/job1",
}
SAMPLE_RESPONSE = {"results": [SAMPLE_JOB], "count": 1}


@pytest.mark.asyncio
async def test_adzuna_fetches_with_country_prefixed_id() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = AdzunaAdapter(
        http_client=client, base_url=BASE_URL, app_id="id", app_key="key", countries=["mx"]
    )
    jobs = await adapter.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].source == "adzuna"
    assert jobs[0].source_id == "mx-job1"
    assert jobs[0].raw_data["country"] == "mx"
    assert client.urls[0] == f"{BASE_URL}/mx/search/1"
    assert client.last_params["app_id"] == "id"
    assert client.last_params["app_key"] == "key"
    assert client.last_params["what"] == "software developer"


@pytest.mark.asyncio
async def test_adzuna_iterates_countries() -> None:
    client = FakeHttpClient({"results": [], "count": 0})
    adapter = AdzunaAdapter(
        http_client=client,
        base_url=BASE_URL,
        app_id="id",
        app_key="key",
        countries=["mx", "br"],
    )
    await adapter.fetch_jobs()
    # Empty first page per country → one call each, no further pages.
    assert client.urls == [f"{BASE_URL}/mx/search/1", f"{BASE_URL}/br/search/1"]


def test_adzuna_source_metadata() -> None:
    adapter = AdzunaAdapter(http_client=None, base_url=BASE_URL, app_id="i", app_key="k")
    assert adapter.source_name() == "adzuna"
    assert adapter.source_type() == SourceType.API
    assert adapter.supports_snapshot_closure() is False


def test_adzuna_normalizer_with_salary() -> None:
    raw = RawJobListing(
        source="adzuna", source_id="mx-job1", raw_data={**SAMPLE_JOB, "country": "mx"}
    )
    result = AdzunaNormalizer().normalize(raw)
    assert result["title"] == "Backend Developer"
    assert result["company"] == "Acme MX"
    assert result["salary_range"] == "MXN 50000-70000"
    assert result["location"] == "Ciudad de México, MX"
    assert result["countries"] == ["Mexico"]
    assert result["url"] == "https://www.adzuna.com.mx/jobs/details/job1"
    assert result["posted_date"] == "2026-03-01T12:00:00Z"
    assert result["skills"] == ["IT Jobs"]
    assert result["remote_modality"] is None
    assert "Build services" in result["description"]


def test_adzuna_normalizer_detects_remote_in_title() -> None:
    raw = RawJobListing(
        source="adzuna",
        source_id="mx-2",
        raw_data={
            "id": "2",
            "title": "Remote Python Engineer",
            "country": "mx",
            "location": {"display_name": "Anywhere"},
        },
    )
    result = AdzunaNormalizer().normalize(raw)
    assert result["remote_modality"] == "remote"


@pytest.mark.asyncio
async def test_adzuna_skipped_when_keys_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adzuna enabled but unconfigured must not break app startup."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("PORTFOLIO_SOURCES", "")
    monkeypatch.setenv("ENABLED_JOB_SOURCES", "adzuna")
    monkeypatch.setenv("ADZUNA_APP_ID", "")
    monkeypatch.setenv("ADZUNA_APP_KEY", "")

    from hiresense.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app), AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200

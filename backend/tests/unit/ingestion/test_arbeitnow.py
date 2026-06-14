from __future__ import annotations

from datetime import datetime

import pytest

from hiresense.ingestion.adapters import ArbeitnowAdapter
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import ArbeitnowNormalizer
from hiresense.kernel.value_objects import SourceType

BASE_URL = "https://www.arbeitnow.com/api/job-board-api"


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
        self.last_params: dict | None = None
        self.calls = 0

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.last_params = kwargs.get("params")
        self.calls += 1
        return FakeResponse(self._data)


SAMPLE_JOB = {
    "slug": "backend-eng-acme-123",
    "company_name": "Acme",
    "title": "Backend Engineer",
    "description": "<p>Build APIs</p>",
    "remote": True,
    "url": "https://www.arbeitnow.com/jobs/companies/acme/backend-eng-123",
    "tags": ["Python", "FastAPI"],
    "job_types": ["full-time"],
    "location": "Berlin",
    "created_at": 1781397033,
}
SAMPLE_RESPONSE = {"data": [SAMPLE_JOB], "links": {"next": None}, "meta": {}}


@pytest.mark.asyncio
async def test_arbeitnow_fetches_jobs() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = ArbeitnowAdapter(http_client=client, base_url=BASE_URL)
    jobs = await adapter.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].source == "arbeitnow"
    assert jobs[0].source_id == "backend-eng-acme-123"


@pytest.mark.asyncio
async def test_arbeitnow_stops_without_next_link() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = ArbeitnowAdapter(http_client=client, base_url=BASE_URL)
    await adapter.fetch_jobs()
    assert client.calls == 1


@pytest.mark.asyncio
async def test_arbeitnow_handles_empty() -> None:
    client = FakeHttpClient({"data": [], "links": {}})
    adapter = ArbeitnowAdapter(http_client=client, base_url=BASE_URL)
    assert await adapter.fetch_jobs() == []


def test_arbeitnow_source_metadata() -> None:
    adapter = ArbeitnowAdapter(http_client=None, base_url=BASE_URL)
    assert adapter.source_name() == "arbeitnow"
    assert adapter.source_type() == SourceType.API
    assert adapter.supports_snapshot_closure() is False


def test_arbeitnow_normalizer_remote() -> None:
    raw = RawJobListing(source="arbeitnow", source_id="x", raw_data=SAMPLE_JOB)
    result = ArbeitnowNormalizer().normalize(raw)
    assert result["title"] == "Backend Engineer"
    assert result["company"] == "Acme"
    assert result["remote_modality"] == "remote"
    assert result["location"] == "Berlin (Remote)"
    assert result["skills"] == ["Python", "FastAPI"]
    assert "Build APIs" in result["description"]
    assert isinstance(result["posted_date"], datetime)


def test_arbeitnow_normalizer_on_site() -> None:
    raw = RawJobListing(
        source="arbeitnow",
        source_id="y",
        raw_data={**SAMPLE_JOB, "remote": False},
    )
    result = ArbeitnowNormalizer().normalize(raw)
    assert result["remote_modality"] == "on_site"
    assert result["location"] == "Berlin"

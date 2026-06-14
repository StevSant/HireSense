from __future__ import annotations

import pytest

from hiresense.ingestion.adapters import SmartRecruitersAdapter
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import SmartRecruitersNormalizer
from hiresense.kernel.value_objects import SourceType

BASE_URL = "https://api.smartrecruiters.com/v1/companies"


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
        self.last_url: str | None = None
        self.last_params: dict | None = None
        self.calls = 0

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.last_url = url
        self.last_params = kwargs.get("params")
        self.calls += 1
        return FakeResponse(self._data)


SAMPLE_POSTING = {
    "id": "uuid-1",
    "name": "Data Engineer",
    "releasedDate": "2026-03-01T00:00:00.000Z",
    "location": {"city": "Berlin", "region": "BE", "country": "de", "remote": False},
    "department": {"label": "Data"},
}
SAMPLE_RESPONSE = {"content": [SAMPLE_POSTING], "totalFound": 1, "offset": 0, "limit": 100}


@pytest.mark.asyncio
async def test_smartrecruiters_fetches_and_builds_public_url() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = SmartRecruitersAdapter(http_client=client, base_url=BASE_URL, timeout=10.0)
    jobs = await adapter.fetch_jobs(board_id="acme", company_name="Acme Corp")
    assert len(jobs) == 1
    assert jobs[0].source == "smartrecruiters"
    assert jobs[0].source_id == "uuid-1"
    assert jobs[0].raw_data["public_url"] == "https://jobs.smartrecruiters.com/acme/uuid-1"
    assert client.last_url == f"{BASE_URL}/acme/postings"
    assert client.last_params == {"offset": "0", "limit": "100"}


@pytest.mark.asyncio
async def test_smartrecruiters_stops_when_total_reached() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = SmartRecruitersAdapter(http_client=client, base_url=BASE_URL, timeout=10.0)
    await adapter.fetch_jobs(board_id="acme", company_name="Acme Corp")
    assert client.calls == 1


@pytest.mark.asyncio
async def test_smartrecruiters_handles_empty() -> None:
    client = FakeHttpClient({"content": [], "totalFound": 0})
    adapter = SmartRecruitersAdapter(http_client=client, base_url=BASE_URL, timeout=10.0)
    assert await adapter.fetch_jobs(board_id="x", company_name="X") == []


def test_smartrecruiters_source_metadata() -> None:
    adapter = SmartRecruitersAdapter(http_client=None, base_url=BASE_URL, timeout=10.0)
    assert adapter.source_name() == "smartrecruiters"
    assert adapter.source_type() == SourceType.API
    assert adapter.supports_snapshot_closure() is True


def test_smartrecruiters_normalizer() -> None:
    raw = RawJobListing(
        source="smartrecruiters",
        source_id="uuid-1",
        raw_data={
            **SAMPLE_POSTING,
            "company": "Acme Corp",
            "public_url": "https://jobs.smartrecruiters.com/acme/uuid-1",
        },
    )
    result = SmartRecruitersNormalizer().normalize(raw)
    assert result["title"] == "Data Engineer"
    assert result["company"] == "Acme Corp"
    assert result["location"] == "Berlin, BE, de"
    assert result["remote_modality"] == "on_site"
    assert result["url"] == "https://jobs.smartrecruiters.com/acme/uuid-1"
    assert result["posted_date"] == "2026-03-01T00:00:00.000Z"
    assert result["department"] == "Data"
    assert result["countries"] == ["DE"]


def test_smartrecruiters_normalizer_remote() -> None:
    raw = RawJobListing(
        source="smartrecruiters",
        source_id="uuid-2",
        raw_data={
            "name": "Remote Dev",
            "company": "Acme Corp",
            "location": {"city": "", "country": "us", "remote": True},
            "public_url": "https://jobs.smartrecruiters.com/acme/uuid-2",
        },
    )
    result = SmartRecruitersNormalizer().normalize(raw)
    assert result["remote_modality"] == "remote"
    assert "Remote" in result["location"]

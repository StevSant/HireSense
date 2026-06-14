from __future__ import annotations

import pytest

from hiresense.ingestion.adapters import WorkableAdapter
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import WorkableNormalizer
from hiresense.kernel.value_objects import SourceType

BASE_URL = "https://apply.workable.com/api/v1/widget/accounts"


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

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.last_url = url
        self.last_params = kwargs.get("params")
        return FakeResponse(self._data)


SAMPLE_JOB = {
    "title": "Senior Backend Engineer",
    "shortcode": "ABC123",
    "telecommuting": True,
    "department": "Engineering",
    "url": "https://apply.workable.com/acme/j/ABC123/",
    "shortlink": "https://apply.workable.com/j/ABC123",
    "published_on": "2026-03-01",
    "country": "United States",
    "city": "New York",
    "state": "NY",
    "description": "<p>Build APIs</p>",
    "requirements": "<p>5y Python</p>",
}
SAMPLE_RESPONSE = {"name": "Acme", "jobs": [SAMPLE_JOB]}


@pytest.mark.asyncio
async def test_workable_fetches_jobs() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = WorkableAdapter(http_client=client, base_url=BASE_URL, timeout=10.0)
    jobs = await adapter.fetch_jobs(board_id="acme", company_name="Acme Corp")
    assert len(jobs) == 1
    assert jobs[0].source == "workable"
    assert jobs[0].source_id == "ABC123"
    assert jobs[0].raw_data["company"] == "Acme Corp"


@pytest.mark.asyncio
async def test_workable_builds_url_with_details() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = WorkableAdapter(http_client=client, base_url=BASE_URL, timeout=10.0)
    await adapter.fetch_jobs(board_id="acme", company_name="Acme Corp")
    assert client.last_url == f"{BASE_URL}/acme"
    assert client.last_params == {"details": "true"}


@pytest.mark.asyncio
async def test_workable_handles_empty_board() -> None:
    client = FakeHttpClient({"jobs": []})
    adapter = WorkableAdapter(http_client=client, base_url=BASE_URL, timeout=10.0)
    assert await adapter.fetch_jobs(board_id="x", company_name="X") == []


def test_workable_source_metadata() -> None:
    adapter = WorkableAdapter(http_client=None, base_url=BASE_URL, timeout=10.0)
    assert adapter.source_name() == "workable"
    assert adapter.source_type() == SourceType.API
    assert adapter.supports_snapshot_closure() is True


def _raw(overrides: dict | None = None) -> RawJobListing:
    data = {**SAMPLE_JOB, "company": "Acme Corp"}
    if overrides:
        data.update(overrides)
    return RawJobListing(source="workable", source_id="ABC123", raw_data=data)


def test_workable_normalizer_remote() -> None:
    result = WorkableNormalizer().normalize(_raw())
    assert result["title"] == "Senior Backend Engineer"
    assert result["company"] == "Acme Corp"
    assert result["remote_modality"] == "remote"
    assert result["location"] == "New York, NY, United States (Remote)"
    assert "Build APIs" in result["description"]
    assert "5y Python" in result["description"]
    assert result["department"] == "Engineering"
    assert result["posted_date"] == "2026-03-01"
    assert result["countries"] == ["United States"]


def test_workable_normalizer_on_site() -> None:
    result = WorkableNormalizer().normalize(_raw({"telecommuting": False}))
    assert result["remote_modality"] == "on_site"
    assert result["location"] == "New York, NY, United States"

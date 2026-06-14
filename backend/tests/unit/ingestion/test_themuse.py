from __future__ import annotations

import pytest

from hiresense.ingestion.adapters import TheMuseAdapter
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import TheMuseNormalizer
from hiresense.kernel.value_objects import SourceType

BASE_URL = "https://www.themuse.com/api/public/jobs"


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
        self.last_params: list | None = None
        self.calls = 0

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.last_params = kwargs.get("params")
        self.calls += 1
        return FakeResponse(self._data)


SAMPLE_RESULT = {
    "id": 123,
    "name": "Software Engineer",
    "contents": "<p>Write code</p>",
    "company": {"name": "Acme"},
    "locations": [{"name": "Flexible / Remote"}],
    "levels": [{"name": "Mid Level"}],
    "categories": [{"name": "Software Engineering"}],
    "refs": {"landing_page": "https://www.themuse.com/jobs/acme/swe"},
    "publication_date": "2026-03-17T13:37:16Z",
}
SAMPLE_RESPONSE = {"page": 1, "page_count": 1, "results": [SAMPLE_RESULT]}


@pytest.mark.asyncio
async def test_themuse_fetches_jobs() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = TheMuseAdapter(
        http_client=client, base_url=BASE_URL, categories=["Software Engineering"]
    )
    jobs = await adapter.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].source == "themuse"
    assert jobs[0].source_id == "123"
    assert ("category", "Software Engineering") in client.last_params
    assert ("page", "1") in client.last_params
    # No api_key configured → not sent.
    assert all(k != "api_key" for k, _ in client.last_params)


@pytest.mark.asyncio
async def test_themuse_sends_api_key_when_set() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = TheMuseAdapter(http_client=client, base_url=BASE_URL, api_key="secret")
    await adapter.fetch_jobs()
    assert ("api_key", "secret") in client.last_params


@pytest.mark.asyncio
async def test_themuse_stops_at_page_count() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = TheMuseAdapter(http_client=client, base_url=BASE_URL)
    await adapter.fetch_jobs()
    assert client.calls == 1


@pytest.mark.asyncio
async def test_themuse_handles_empty() -> None:
    client = FakeHttpClient({"results": [], "page_count": 1})
    adapter = TheMuseAdapter(http_client=client, base_url=BASE_URL)
    assert await adapter.fetch_jobs() == []


def test_themuse_source_metadata() -> None:
    adapter = TheMuseAdapter(http_client=None, base_url=BASE_URL)
    assert adapter.source_name() == "themuse"
    assert adapter.source_type() == SourceType.API
    assert adapter.supports_snapshot_closure() is False


def test_themuse_normalizer() -> None:
    raw = RawJobListing(source="themuse", source_id="123", raw_data=SAMPLE_RESULT)
    result = TheMuseNormalizer().normalize(raw)
    assert result["title"] == "Software Engineer"
    assert result["company"] == "Acme"
    assert result["remote_modality"] == "remote"
    assert result["location"] == "Flexible / Remote"
    assert result["skills"] == ["Software Engineering", "Mid Level"]
    assert result["url"] == "https://www.themuse.com/jobs/acme/swe"
    assert "Write code" in result["description"]
    assert result["posted_date"] == "2026-03-17T13:37:16Z"


def test_themuse_normalizer_on_site() -> None:
    raw = RawJobListing(
        source="themuse",
        source_id="124",
        raw_data={**SAMPLE_RESULT, "locations": [{"name": "Berlin, Germany"}]},
    )
    result = TheMuseNormalizer().normalize(raw)
    assert result["remote_modality"] == "on_site"
    assert result["location"] == "Berlin, Germany"

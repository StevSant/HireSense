import pytest
from hiresense.ingestion.adapters.remoteok import RemoteOKAdapter
from hiresense.kernel.value_objects import SourceType


class FakeResponse:
    def __init__(self, data: list) -> None:
        self._data = data
        self.status_code = 200

    def json(self) -> list:
        return self._data

    def raise_for_status(self) -> None:
        pass


TEST_URL = "https://test.example/api"


class FakeHttpClient:
    def __init__(self, response_data: list) -> None:
        self._response_data = response_data
        self.last_url: str | None = None

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.last_url = url
        return FakeResponse(self._response_data)


@pytest.mark.asyncio
async def test_remoteok_fetches_and_normalizes() -> None:
    sample_response = [
        {"legal": "This is a legal notice"},
        {
            "id": "67890",
            "position": "Python Developer",
            "company": "StartupX",
            "description": "Join our team to build AI tools",
            "tags": ["python", "ai", "fastapi"],
            "location": "Worldwide",
            "salary_min": 80000,
            "salary_max": 120000,
            "url": "https://remoteok.com/l/67890",
            "date": "2026-03-27T10:00:00",
        },
    ]
    client = FakeHttpClient(sample_response)
    adapter = RemoteOKAdapter(http_client=client, base_url=TEST_URL)
    jobs = await adapter.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].source == "remoteok"
    assert jobs[0].source_id == "67890"
    assert jobs[0].raw_data["position"] == "Python Developer"


@pytest.mark.asyncio
async def test_remoteok_uses_configured_base_url() -> None:
    client = FakeHttpClient([])
    adapter = RemoteOKAdapter(http_client=client, base_url=TEST_URL)
    await adapter.fetch_jobs()
    assert client.last_url == TEST_URL


def test_remoteok_source_name() -> None:
    adapter = RemoteOKAdapter(http_client=None, base_url=TEST_URL)
    assert adapter.source_name() == "remoteok"
    assert adapter.source_type() == SourceType.API

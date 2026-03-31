import pytest
from hiresense.ingestion.adapters.remotive import RemotiveAdapter
from hiresense.kernel.value_objects import SourceType


class FakeResponse:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.status_code = 200
    def json(self) -> dict:
        return self._data
    def raise_for_status(self) -> None:
        pass


class FakeHttpClient:
    def __init__(self, response_data: dict) -> None:
        self._response_data = response_data
    async def get(self, url: str, **kwargs) -> FakeResponse:
        return FakeResponse(self._response_data)


@pytest.mark.asyncio
async def test_remotive_fetches_and_normalizes() -> None:
    sample_response = {
        "jobs": [
            {
                "id": 12345,
                "title": "Backend Engineer",
                "company_name": "Acme",
                "description": "<p>Build APIs with FastAPI</p>",
                "tags": ["python", "fastapi"],
                "candidate_required_location": "Worldwide",
                "salary": "$80k - $120k",
                "url": "https://remotive.com/remote-jobs/12345",
                "publication_date": "2026-03-28T12:00:00",
                "category": "Software Development",
            }
        ]
    }
    client = FakeHttpClient(sample_response)
    adapter = RemotiveAdapter(http_client=client)
    jobs = await adapter.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].source == "remotive"
    assert jobs[0].source_id == "12345"
    assert jobs[0].raw_data["title"] == "Backend Engineer"


def test_remotive_source_name() -> None:
    adapter = RemotiveAdapter(http_client=None)
    assert adapter.source_name() == "remotive"
    assert adapter.source_type() == SourceType.API

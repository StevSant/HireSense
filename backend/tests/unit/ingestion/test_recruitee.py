from __future__ import annotations

import pytest

from hiresense.ingestion.adapters import RecruiteeAdapter
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import RecruiteeNormalizer
from hiresense.kernel.value_objects import SourceType

BASE_URL = "https://{company}.recruitee.com/api"


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

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.last_url = url
        return FakeResponse(self._data)


SAMPLE_OFFER = {
    "id": 555,
    "title": "Frontend Developer",
    "description": "<p>React work</p>",
    "requirements": "<p>3y JS</p>",
    "department": "Engineering",
    "published_at": "2026-03-01T10:00:00.000+01:00",
    "country_code": "nl",
    "city": "Amsterdam",
    "location": "Amsterdam, Netherlands",
    "remote": True,
    "careers_url": "https://acme.recruitee.com/o/frontend-developer",
    "salary": {"min": 50000, "max": 70000, "currency": "EUR"},
}
SAMPLE_RESPONSE = {"offers": [SAMPLE_OFFER]}


@pytest.mark.asyncio
async def test_recruitee_fetches_and_builds_subdomain_url() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = RecruiteeAdapter(http_client=client, base_url=BASE_URL, timeout=10.0)
    jobs = await adapter.fetch_jobs(board_id="acme", company_name="Acme Corp")
    assert len(jobs) == 1
    assert jobs[0].source == "recruitee"
    assert jobs[0].source_id == "555"
    assert jobs[0].raw_data["company"] == "Acme Corp"
    assert client.last_url == "https://acme.recruitee.com/api/offers/"


@pytest.mark.asyncio
async def test_recruitee_handles_empty() -> None:
    client = FakeHttpClient({"offers": []})
    adapter = RecruiteeAdapter(http_client=client, base_url=BASE_URL, timeout=10.0)
    assert await adapter.fetch_jobs(board_id="x", company_name="X") == []


def test_recruitee_source_metadata() -> None:
    adapter = RecruiteeAdapter(http_client=None, base_url=BASE_URL, timeout=10.0)
    assert adapter.source_name() == "recruitee"
    assert adapter.source_type() == SourceType.API
    assert adapter.supports_snapshot_closure() is True


def test_recruitee_normalizer() -> None:
    raw = RawJobListing(
        source="recruitee",
        source_id="555",
        raw_data={**SAMPLE_OFFER, "company": "Acme Corp"},
    )
    result = RecruiteeNormalizer().normalize(raw)
    assert result["title"] == "Frontend Developer"
    assert result["company"] == "Acme Corp"
    assert result["remote_modality"] == "remote"
    assert result["location"] == "Amsterdam, Netherlands (Remote)"
    assert result["salary_range"] == "EUR 50000-70000"
    assert result["url"] == "https://acme.recruitee.com/o/frontend-developer"
    assert result["department"] == "Engineering"
    assert result["countries"] == ["NL"]
    assert "React work" in result["description"]
    assert "3y JS" in result["description"]


def test_recruitee_normalizer_no_salary_on_site() -> None:
    raw = RawJobListing(
        source="recruitee",
        source_id="556",
        raw_data={
            "id": 556,
            "title": "Onsite Dev",
            "company": "Acme Corp",
            "country_code": "de",
            "city": "Berlin",
            "remote": False,
        },
    )
    result = RecruiteeNormalizer().normalize(raw)
    assert result["salary_range"] is None
    assert result["remote_modality"] == "on_site"
    assert result["location"] == "Berlin, de"

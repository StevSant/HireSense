from __future__ import annotations

import pytest
from hiresense.ingestion.adapters.lever_adapter import LeverAdapter
from hiresense.ingestion.domain.normalizers.lever_normalizer import LeverNormalizer
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, data: list) -> None:
        self._data = data
        self.status_code = 200

    def json(self) -> list:
        return self._data

    def raise_for_status(self) -> None:
        pass


class FakeHttpClient:
    def __init__(self, response_data: list) -> None:
        self._response_data = response_data
        self.last_url: str | None = None
        self.last_params: dict | None = None

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.last_url = url
        self.last_params = kwargs.get("params")
        return FakeResponse(self._response_data)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_POSTING = {
    "id": "abc-123",
    "text": "Frontend Engineer",
    "categories": {"location": "New York, NY", "team": "Product"},
    "description": "<p>Build UIs with React</p>",
    "hostedUrl": "https://jobs.lever.co/retool/abc-123",
    "createdAt": 1711699200000,
}

SAMPLE_RESPONSE = [SAMPLE_POSTING]


# ---------------------------------------------------------------------------
# Adapter tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lever_fetches_jobs() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = LeverAdapter(
        http_client=client,
        base_url="https://api.lever.co/v0/postings",
        timeout=10.0,
    )
    jobs = await adapter.fetch_jobs(board_id="retool", company_name="Retool")
    assert len(jobs) == 1
    assert jobs[0].source == "lever"
    assert jobs[0].source_id == "abc-123"
    assert jobs[0].raw_data["text"] == "Frontend Engineer"
    assert jobs[0].raw_data["company"] == "Retool"


@pytest.mark.asyncio
async def test_lever_builds_correct_url() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = LeverAdapter(
        http_client=client,
        base_url="https://api.lever.co/v0/postings",
        timeout=10.0,
    )
    await adapter.fetch_jobs(board_id="retool", company_name="Retool")
    assert client.last_url == "https://api.lever.co/v0/postings/retool"
    assert client.last_params == {"mode": "json"}


@pytest.mark.asyncio
async def test_lever_handles_empty_board() -> None:
    client = FakeHttpClient([])
    adapter = LeverAdapter(
        http_client=client,
        base_url="https://api.lever.co/v0/postings",
        timeout=10.0,
    )
    jobs = await adapter.fetch_jobs(board_id="empty-co", company_name="Empty Co")
    assert jobs == []


def test_lever_source_metadata() -> None:
    adapter = LeverAdapter(
        http_client=None,
        base_url="https://api.lever.co/v0/postings",
        timeout=10.0,
    )
    assert adapter.source_name() == "lever"
    assert adapter.source_type() == SourceType.API


# ---------------------------------------------------------------------------
# Normalizer tests
# ---------------------------------------------------------------------------

def _make_raw(overrides: dict | None = None) -> RawJobListing:
    data = {**SAMPLE_POSTING, "company": "Retool"}
    if overrides:
        data.update(overrides)
    return RawJobListing(source="lever", source_id="abc-123", raw_data=data)


def test_lever_normalizer_full_data() -> None:
    normalizer = LeverNormalizer()
    result = normalizer.normalize(_make_raw())

    assert result["title"] == "Frontend Engineer"
    assert result["company"] == "Retool"
    assert "Build UIs with React" in result["description"]
    assert "<p>" not in result["description"]
    assert result["skills"] == []
    assert result["location"] == "New York, NY"
    assert result["salary_range"] is None
    assert result["url"] == "https://jobs.lever.co/retool/abc-123"
    assert result["language"] == "en"
    assert result["posted_date"] == "2024-03-29T08:00:00+00:00"
    assert result["department"] == "Product"


def test_lever_normalizer_strips_html() -> None:
    normalizer = LeverNormalizer()
    result = normalizer.normalize(_make_raw({"description": "<p>Line one</p><p>Line two</p>"}))
    assert "<p>" not in result["description"]
    assert "Line one" in result["description"]
    assert "Line two" in result["description"]


def test_lever_normalizer_missing_categories() -> None:
    normalizer = LeverNormalizer()
    result = normalizer.normalize(_make_raw({"categories": {}}))
    assert result["location"] == ""
    assert result["department"] is None


def test_lever_normalizer_no_categories_key() -> None:
    normalizer = LeverNormalizer()
    raw_data = {k: v for k, v in {**SAMPLE_POSTING, "company": "Retool"}.items() if k != "categories"}
    raw = RawJobListing(source="lever", source_id="abc-123", raw_data=raw_data)
    result = normalizer.normalize(raw)
    assert result["location"] == ""
    assert result["department"] is None


def test_lever_normalizer_missing_created_at() -> None:
    normalizer = LeverNormalizer()
    result = normalizer.normalize(_make_raw({"createdAt": None}))
    assert result["posted_date"] is None


def test_lever_normalizer_no_created_at_key() -> None:
    normalizer = LeverNormalizer()
    raw_data = {k: v for k, v in {**SAMPLE_POSTING, "company": "Retool"}.items() if k != "createdAt"}
    raw = RawJobListing(source="lever", source_id="abc-123", raw_data=raw_data)
    result = normalizer.normalize(raw)
    assert result["posted_date"] is None

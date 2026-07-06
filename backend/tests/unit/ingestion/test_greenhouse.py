from __future__ import annotations

import pytest
from hiresense.ingestion.adapters.greenhouse_adapter import GreenhouseAdapter
from hiresense.ingestion.domain.normalizers.greenhouse_normalizer import GreenhouseNormalizer
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


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
        self.last_url: str | None = None
        self.last_params: dict | None = None

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.last_url = url
        self.last_params = kwargs.get("params")
        return FakeResponse(self._response_data)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_JOB = {
    "id": 4001,
    "title": "Senior Python Engineer",
    "content": "<p>Build backend systems with FastAPI.</p>",
    "absolute_url": "https://boards.greenhouse.io/acme/jobs/4001",
    "location": {"name": "Remote — Americas"},
    "departments": [{"id": 1, "name": "Engineering"}],
    "updated_at": "2026-03-28T10:00:00.000Z",
}

SAMPLE_RESPONSE = {"jobs": [SAMPLE_JOB]}


# ---------------------------------------------------------------------------
# Adapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_greenhouse_fetches_jobs() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = GreenhouseAdapter(
        http_client=client,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        timeout=10.0,
    )
    jobs = await adapter.fetch_jobs(board_id="acme", company_name="Acme Corp")
    assert len(jobs) == 1
    assert jobs[0].source == "greenhouse"
    assert jobs[0].source_id == "4001"
    assert jobs[0].raw_data["title"] == "Senior Python Engineer"
    assert jobs[0].raw_data["company"] == "Acme Corp"


@pytest.mark.asyncio
async def test_greenhouse_builds_correct_url() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = GreenhouseAdapter(
        http_client=client,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        timeout=10.0,
    )
    await adapter.fetch_jobs(board_id="acme", company_name="Acme Corp")
    assert client.last_url == "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    assert client.last_params == {"content": "true"}


@pytest.mark.asyncio
async def test_greenhouse_handles_empty_board() -> None:
    client = FakeHttpClient({"jobs": []})
    adapter = GreenhouseAdapter(
        http_client=client,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        timeout=10.0,
    )
    jobs = await adapter.fetch_jobs(board_id="empty-co", company_name="Empty Co")
    assert jobs == []


def test_greenhouse_source_metadata() -> None:
    adapter = GreenhouseAdapter(
        http_client=None,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        timeout=10.0,
    )
    assert adapter.source_name() == "greenhouse"
    assert adapter.source_type() == SourceType.API


# ---------------------------------------------------------------------------
# Normalizer tests
# ---------------------------------------------------------------------------


def _make_raw(overrides: dict | None = None) -> RawJobListing:
    data = {**SAMPLE_JOB, "company": "Acme Corp"}
    if overrides:
        data.update(overrides)
    return RawJobListing(source="greenhouse", source_id="4001", raw_data=data)


def test_greenhouse_normalizer_full_data() -> None:
    normalizer = GreenhouseNormalizer()
    result = normalizer.normalize(_make_raw())

    assert result["title"] == "Senior Python Engineer"
    assert result["company"] == "Acme Corp"
    assert "Build backend systems with FastAPI" in result["description"]
    assert result["skills"] == []
    assert result["location"] == "Remote — Americas"
    assert result["salary_range"] is None
    assert result["url"] == "https://boards.greenhouse.io/acme/jobs/4001"
    assert result["language"] == "en"
    assert result["posted_date"] == "2026-03-28T10:00:00.000Z"
    assert result["department"] == "Engineering"


def test_greenhouse_normalizer_missing_location() -> None:
    normalizer = GreenhouseNormalizer()
    result = normalizer.normalize(_make_raw({"location": None}))
    assert result["location"] == ""


def test_greenhouse_normalizer_missing_departments() -> None:
    normalizer = GreenhouseNormalizer()
    result = normalizer.normalize(_make_raw({"departments": []}))
    assert result["department"] is None


def test_greenhouse_normalizer_no_departments_key() -> None:
    normalizer = GreenhouseNormalizer()
    raw_data = {
        k: v for k, v in {**SAMPLE_JOB, "company": "Acme Corp"}.items() if k != "departments"
    }
    raw = RawJobListing(source="greenhouse", source_id="4001", raw_data=raw_data)
    result = normalizer.normalize(raw)
    assert result["department"] is None


def test_greenhouse_normalizer_strips_html() -> None:
    normalizer = GreenhouseNormalizer()
    result = normalizer.normalize(_make_raw({"content": "<p>Line one</p><p>Line two</p>"}))
    assert "<p>" not in result["description"]
    assert "Line one" in result["description"]
    assert "Line two" in result["description"]


def test_greenhouse_supports_snapshot_closure() -> None:
    adapter = GreenhouseAdapter(
        http_client=None,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        timeout=10.0,
    )
    assert adapter.supports_snapshot_closure() is True

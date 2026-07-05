from __future__ import annotations

import pytest
from hiresense.ingestion.adapters.ashby_adapter import AshbyAdapter
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
        self.last_kwargs: dict | None = None

    async def post(self, url: str, **kwargs) -> FakeResponse:
        self.last_url = url
        self.last_kwargs = kwargs
        return FakeResponse(self._response_data)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_JOB = {
    "id": "job-001",
    "title": "AI Engineer",
    "location": "Remote - US",
    "descriptionHtml": "<p>Work on <b>voice synthesis</b></p>",
    "jobUrl": "https://jobs.ashbyhq.com/elevenlabs/job-001",
    "publishedAt": "2026-04-01T00:00:00.000Z",
    "departmentName": "AI Team",
}

SAMPLE_RESPONSE = {"jobs": [SAMPLE_JOB]}


# ---------------------------------------------------------------------------
# Adapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ashby_fetches_jobs() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = AshbyAdapter(
        http_client=client,
        base_url="https://api.ashbyhq.com/posting-api/job-board",
        timeout=10.0,
    )
    jobs = await adapter.fetch_jobs(board_id="elevenlabs", company_name="ElevenLabs")
    assert len(jobs) == 1
    assert jobs[0].source == "ashby"
    assert jobs[0].source_id == "job-001"
    assert jobs[0].raw_data["title"] == "AI Engineer"
    assert jobs[0].raw_data["company"] == "ElevenLabs"


@pytest.mark.asyncio
async def test_ashby_uses_post_method() -> None:
    client = FakeHttpClient(SAMPLE_RESPONSE)
    adapter = AshbyAdapter(
        http_client=client,
        base_url="https://api.ashbyhq.com/posting-api/job-board",
        timeout=10.0,
    )
    await adapter.fetch_jobs(board_id="elevenlabs", company_name="ElevenLabs")
    assert client.last_url == "https://api.ashbyhq.com/posting-api/job-board/elevenlabs"


@pytest.mark.asyncio
async def test_ashby_handles_empty_board() -> None:
    client = FakeHttpClient({"jobs": []})
    adapter = AshbyAdapter(
        http_client=client,
        base_url="https://api.ashbyhq.com/posting-api/job-board",
        timeout=10.0,
    )
    jobs = await adapter.fetch_jobs(board_id="empty-co", company_name="Empty Co")
    assert jobs == []


def test_ashby_source_metadata() -> None:
    adapter = AshbyAdapter(
        http_client=None,
        base_url="https://api.ashbyhq.com/posting-api/job-board",
        timeout=10.0,
    )
    assert adapter.source_name() == "ashby"
    assert adapter.source_type() == SourceType.API


# ---------------------------------------------------------------------------
# Normalizer tests
# ---------------------------------------------------------------------------

from hiresense.ingestion.domain.normalizers.ashby_normalizer import AshbyNormalizer  # noqa: E402


def _make_raw(overrides: dict | None = None) -> RawJobListing:
    data = {**SAMPLE_JOB, "company": "ElevenLabs"}
    if overrides:
        data.update(overrides)
    return RawJobListing(source="ashby", source_id="job-001", raw_data=data)


def test_ashby_normalizer_full_data() -> None:
    normalizer = AshbyNormalizer()
    result = normalizer.normalize(_make_raw())

    assert result["title"] == "AI Engineer"
    assert result["company"] == "ElevenLabs"
    assert "voice synthesis" in result["description"]
    assert "<p>" not in result["description"]
    assert result["skills"] == []
    assert result["location"] == "Remote - US"
    assert result["salary_range"] is None
    assert result["url"] == "https://jobs.ashbyhq.com/elevenlabs/job-001"
    assert result["language"] == "en"
    assert result["posted_date"] == "2026-04-01T00:00:00.000Z"
    assert result["department"] == "AI Team"


def test_ashby_normalizer_strips_html() -> None:
    normalizer = AshbyNormalizer()
    result = normalizer.normalize(_make_raw({"descriptionHtml": "<p>Line one</p><p>Line two</p>"}))
    assert "<p>" not in result["description"]
    assert "Line one" in result["description"]
    assert "Line two" in result["description"]


def test_ashby_normalizer_missing_location() -> None:
    normalizer = AshbyNormalizer()
    raw_data = {k: v for k, v in {**SAMPLE_JOB, "company": "ElevenLabs"}.items() if k != "location"}
    raw = RawJobListing(source="ashby", source_id="job-001", raw_data=raw_data)
    result = normalizer.normalize(raw)
    assert result["location"] == ""


def test_ashby_normalizer_missing_published_at() -> None:
    normalizer = AshbyNormalizer()
    raw_data = {
        k: v for k, v in {**SAMPLE_JOB, "company": "ElevenLabs"}.items() if k != "publishedAt"
    }
    raw = RawJobListing(source="ashby", source_id="job-001", raw_data=raw_data)
    result = normalizer.normalize(raw)
    assert result["posted_date"] is None


def test_ashby_normalizer_missing_department() -> None:
    normalizer = AshbyNormalizer()
    raw_data = {
        k: v for k, v in {**SAMPLE_JOB, "company": "ElevenLabs"}.items() if k != "departmentName"
    }
    raw = RawJobListing(source="ashby", source_id="job-001", raw_data=raw_data)
    result = normalizer.normalize(raw)
    assert result["department"] is None

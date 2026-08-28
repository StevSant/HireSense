from __future__ import annotations

import json

import pytest

from hiresense.ingestion.adapters.ziprecruiter import ZipRecruiterAdapter, _extract_jobs
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import ZipRecruiterNormalizer
from hiresense.shared.kernel.value_objects import SourceType


class FakeResponse:
    def __init__(
        self, body: dict | str, status_code: int = 200, headers: dict[str, str] | None = None
    ) -> None:
        self.text = body if isinstance(body, str) else json.dumps(body)
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttpClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if not self._responses:
            raise RuntimeError("no more responses")
        return self._responses.pop(0)


JOB = {
    "jobId": "zr-123",
    "title": "Senior Python Engineer",
    "company": "Acme Labs",
    "description": "<p>Build reliable Python services with a small team.</p>",
    "location": "Remote, United States",
    "salary": "$140,000 - $170,000",
    "employmentType": "Full-Time",
    "isRemote": True,
    "datePosted": "2026-08-20T12:00:00Z",
    "url": "https://www.ziprecruiter.com/job/zr-123?utm_source=feed",
    "applyUrl": "https://www.ziprecruiter.com/job/zr-123/apply",
    "skills": ["Python", "AWS"],
}


def _tool_result(jobs: list[dict]) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [{"type": "text", "text": json.dumps({"jobs": jobs})}],
        },
    }


def test_ziprecruiter_extracts_text_when_structured_content_is_empty() -> None:
    response = _tool_result([JOB])
    response["structuredContent"] = []
    assert _extract_jobs(response) == [JOB]


@pytest.mark.asyncio
async def test_ziprecruiter_fetches_structured_jobs_and_paginates() -> None:
    client = FakeHttpClient(
        [
            FakeResponse(
                {"jsonrpc": "2.0", "id": 1, "result": {}},
                headers={"mcp-session-id": "session-1"},
            ),
            FakeResponse(_tool_result([{**JOB, "jobId": f"zr-{index}"} for index in range(5)])),
            FakeResponse(_tool_result([])),
        ]
    )
    adapter = ZipRecruiterAdapter(
        http_client=client,
        query="python",
        location="Remote",
        country="US",
        remote_only=True,
        page_limit=6,
    )

    jobs = await adapter.fetch_jobs()

    assert len(jobs) == 5
    assert jobs[0].source == "ziprecruiter"
    assert jobs[0].source_id == "zr-0"
    assert adapter.source_type() == SourceType.API
    assert adapter.supports_snapshot_closure() is False
    assert client.calls[1]["json"]["params"]["arguments"] == {
        "keyword": "python",
        "offset": 0,
        "location": "Remote",
        "country": "US",
        "workplace_type": "remote",
    }
    assert client.calls[1]["headers"]["Mcp-Session-Id"] == "session-1"
    assert client.calls[2]["json"]["params"]["arguments"]["offset"] == 1


@pytest.mark.asyncio
async def test_ziprecruiter_keeps_partial_results_on_later_failure() -> None:
    client = FakeHttpClient(
        [
            FakeResponse({"jsonrpc": "2.0", "id": 1, "result": {}}),
            FakeResponse(_tool_result([JOB])),
            FakeResponse("unavailable", status_code=503),
        ]
    )
    jobs = await ZipRecruiterAdapter(http_client=client, page_limit=2).fetch_jobs()
    assert len(jobs) == 1


def test_ziprecruiter_normalizer_maps_common_fields() -> None:
    raw = RawJobListing(source="ziprecruiter", source_id="zr-123", raw_data=JOB)
    out = ZipRecruiterNormalizer().normalize(raw)

    assert out["title"] == "Senior Python Engineer"
    assert out["company"] == "Acme Labs"
    assert out["description"] == "Build reliable Python services with a small team."
    assert out["salary_range"] == "$140,000 - $170,000"
    assert out["employment_type"] == "full_time"
    assert out["remote_modality"] == "remote"
    assert out["skills"] == ["Python", "AWS"]
    assert "utm_" not in out["url"]
    assert out["source_metadata"]["application_url"].endswith("/apply")

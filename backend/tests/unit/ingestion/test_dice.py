from __future__ import annotations

import json

import pytest

from hiresense.ingestion.adapters.dice import DiceAdapter, _parse_sse_jsonrpc
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import DiceNormalizer
from hiresense.kernel.value_objects import SourceType


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return json.loads(self.text)


class FakeHttpClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if not self._responses:
            raise RuntimeError("no more responses")
        return self._responses.pop(0)


def _tool_result(jobs: list[dict], page: int = 1, page_count: int = 1) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "data": jobs,
                            "meta": {
                                "currentPage": page,
                                "pageCount": page_count,
                                "pageSize": len(jobs),
                                "totalResults": len(jobs),
                            },
                        }
                    ),
                }
            ]
        },
    }
    return f"event: message\ndata: {json.dumps(payload)}\n\n"


SAMPLE_JOB = {
    "id": "abc",
    "guid": "03f2f1da-e596-49f0-882f-e0e0a676d946",
    "title": "iOS Software Engineer",
    "summary": "Build apps",
    "postedDate": "2026-07-20T11:03:11Z",
    "detailsPageUrl": "https://www.dice.com/job-detail/03f2f1da?utm_source=x&utm_medium=mcp",
    "salary": "$120,000 - $175,000",
    "companyName": "Next Step Systems",
    "employmentType": "Full-time",
    "easyApply": True,
    "employerType": "Recruiter",
    "workplaceTypes": ["Remote"],
    "isRemote": True,
    "willingToSponsor": False,
}


def test_parse_sse_jsonrpc() -> None:
    body = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'
    assert _parse_sse_jsonrpc(body)["result"]["ok"] is True


@pytest.mark.asyncio
async def test_dice_fetches_jobs() -> None:
    init = FakeResponse('event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\n\n')
    search = FakeResponse(_tool_result([SAMPLE_JOB]))
    client = FakeHttpClient([init, search])
    adapter = DiceAdapter(http_client=client, page_limit=1, jobs_per_page=10)
    jobs = await adapter.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].source == "dice"
    assert jobs[0].source_id == SAMPLE_JOB["guid"]
    assert adapter.source_type() == SourceType.API
    assert adapter.supports_snapshot_closure() is False


@pytest.mark.asyncio
async def test_dice_pagination_stops_on_page_count() -> None:
    init = FakeResponse('{"jsonrpc":"2.0","id":1,"result":{}}')
    page1 = FakeResponse(_tool_result([SAMPLE_JOB], page=1, page_count=1))
    client = FakeHttpClient([init, page1])
    adapter = DiceAdapter(http_client=client, page_limit=5)
    await adapter.fetch_jobs()
    assert adapter.last_pages_fetched == 1


@pytest.mark.asyncio
async def test_dice_empty_results() -> None:
    init = FakeResponse('{"jsonrpc":"2.0","id":1,"result":{}}')
    empty = FakeResponse(_tool_result([]))
    client = FakeHttpClient([init, empty])
    adapter = DiceAdapter(http_client=client)
    assert await adapter.fetch_jobs() == []


@pytest.mark.asyncio
async def test_dice_http_error_propagates() -> None:
    init = FakeResponse('{"jsonrpc":"2.0","id":1,"result":{}}')
    err = FakeResponse("nope", status_code=500)
    client = FakeHttpClient([init, err])
    adapter = DiceAdapter(http_client=client)
    with pytest.raises(RuntimeError):
        await adapter.fetch_jobs()


@pytest.mark.asyncio
async def test_dice_keeps_partial_pages_on_later_failure() -> None:
    init = FakeResponse('{"jsonrpc":"2.0","id":1,"result":{}}')
    page1 = FakeResponse(_tool_result([SAMPLE_JOB], page=1, page_count=3))
    page2 = FakeResponse("nope", status_code=500)
    client = FakeHttpClient([init, page1, page2])
    adapter = DiceAdapter(http_client=client, page_limit=3, jobs_per_page=1)
    jobs = await adapter.fetch_jobs()
    assert len(jobs) == 1
    assert adapter.last_parse_failures >= 1


def test_dice_normalizer_fields() -> None:
    raw = RawJobListing(source="dice", source_id=SAMPLE_JOB["guid"], raw_data=SAMPLE_JOB)
    out = DiceNormalizer().normalize(raw)
    assert out["title"] == "iOS Software Engineer"
    assert out["company"] == "Next Step Systems"
    assert out["salary_range"] == "$120,000 - $175,000"
    assert out["employment_type"] == "full_time"
    assert out["remote_modality"] == "remote"
    assert out["visa_sponsorship_available"] is False
    assert out["source_metadata"]["easy_apply"] is True
    assert out["source_metadata"]["employer_type"] == "Recruiter"
    assert "utm_" not in out["url"]

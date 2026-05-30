from __future__ import annotations

import pytest
from hiresense.ingestion.adapters.hn_hiring import HNHiringAdapter
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


class FakeHNClient:
    """Routes the two calls the adapter makes: thread search, then item fetch."""

    def __init__(self, thread_id: str, children: list[dict]) -> None:
        self._thread_id = thread_id
        self._children = children

    async def get(self, url: str, **kwargs) -> FakeResponse:
        if url.endswith("/search_by_date"):
            return FakeResponse({"hits": [{"objectID": self._thread_id}]})
        return FakeResponse({"children": self._children})


def _comment(comment_id: int, text: str) -> dict:
    return {
        "id": comment_id,
        "type": "comment",
        "author": "someone",
        "text": text,
        "created_at": "2026-05-04T00:00:00Z",
        "created_at_i": 0,
    }


COMPANY_POST = _comment(
    101,
    "Acme Corp | Senior Backend Engineer | Remote (US/EU)"
    "<p>We build cool things. Apply at jobs@acme.com</p>",
)

# A job *seeker* who cross-posted into the 'Who is hiring?' thread by mistake.
SEEKING_WORK_POST = _comment(
    202,
    "SEEKING WORK | Full-Stack Developer (Django, Vue, AWS)"
    "<p>Location: Argentina (remote-friendly, US/EU time overlap)</p>",
)

SEEKING_FREELANCER_POST = _comment(
    303,
    "SEEKING FREELANCER | React, Node | Remote<p>Available 20h/week.</p>",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _adapter(children: list[dict]) -> HNHiringAdapter:
    client = FakeHNClient(thread_id="48012147", children=children)
    return HNHiringAdapter(http_client=client, base_url="https://hn.algolia.com/api/v1")


@pytest.mark.asyncio
async def test_company_posts_are_ingested() -> None:
    jobs = await _adapter([COMPANY_POST]).fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].source_id == "101"


@pytest.mark.asyncio
async def test_seeking_work_posts_are_rejected() -> None:
    """A 'SEEKING WORK' comment is a job seeker, not a job posting."""
    jobs = await _adapter([COMPANY_POST, SEEKING_WORK_POST]).fetch_jobs()
    assert [j.source_id for j in jobs] == ["101"]


@pytest.mark.asyncio
async def test_seeking_freelancer_posts_are_rejected() -> None:
    jobs = await _adapter([COMPANY_POST, SEEKING_FREELANCER_POST]).fetch_jobs()
    assert [j.source_id for j in jobs] == ["101"]


def test_source_metadata() -> None:
    adapter = HNHiringAdapter(http_client=None, base_url="https://x")
    assert adapter.source_name() == "hn_hiring"
    assert adapter.source_type() == SourceType.SCRAPER

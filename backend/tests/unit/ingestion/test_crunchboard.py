from __future__ import annotations

import pytest

from hiresense.ingestion.adapters.crunchboard import CrunchBoardAdapter, parse_crunchboard_title
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import CrunchBoardNormalizer
from hiresense.kernel.value_objects import SourceType

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Latest jobs from Crunchboard Jobs</title>
    <item>
      <guid>https://www.crunchboard.com/jobs/557721087-computer-systems-technician-at-city-of-urbana</guid>
      <link>https://www.crunchboard.com/jobs/557721087-computer-systems-technician-at-city-of-urbana</link>
      <title>Computer/Systems Technician at City of Urbana (Urbana, Illinois, USA)</title>
      <description>Job Type: Full-time. Build systems.</description>
      <pubDate>Wed, 15 Jul 2026 18:51:02 +0000</pubDate>
    </item>
    <item>
      <guid>https://www.crunchboard.com/jobs/dup</guid>
      <link>https://www.crunchboard.com/jobs/dup</link>
      <title>Bad Item</title>
      <description></description>
    </item>
  </channel>
</rss>
"""


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self.status_code = 200

    def raise_for_status(self) -> None:
        pass


class FakeHttpClient:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls += 1
        return FakeResponse(self._text)


def test_parse_title() -> None:
    title, company, location = parse_crunchboard_title("Senior Engineer at Acme (Remote, USA)")
    assert title == "Senior Engineer"
    assert company == "Acme"
    assert location == "Remote, USA"


@pytest.mark.asyncio
async def test_crunchboard_fetches() -> None:
    adapter = CrunchBoardAdapter(http_client=FakeHttpClient(RSS))
    jobs = await adapter.fetch_jobs()
    assert len(jobs) == 2
    assert jobs[0].source == "crunchboard"
    assert "557721087" in jobs[0].source_id
    assert adapter.source_type() == SourceType.RSS
    assert adapter.supports_snapshot_closure() is False


@pytest.mark.asyncio
async def test_crunchboard_empty() -> None:
    empty = """<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>"""
    adapter = CrunchBoardAdapter(http_client=FakeHttpClient(empty))
    assert await adapter.fetch_jobs() == []


def test_crunchboard_normalizer() -> None:
    raw = RawJobListing(
        source="crunchboard",
        source_id="557721087-computer-systems-technician-at-city-of-urbana",
        raw_data={
            "title": "Computer/Systems Technician at City of Urbana (Urbana, Illinois, USA)",
            "link": "https://www.crunchboard.com/jobs/557721087-x",
            "published": "Wed, 15 Jul 2026 18:51:02 +0000",
            "summary": "Job Type: Full-time. Build systems.",
            "tags": [],
        },
    )
    out = CrunchBoardNormalizer().normalize(raw)
    assert out["title"] == "Computer/Systems Technician"
    assert out["company"] == "City of Urbana"
    assert "Urbana" in out["location"]
    assert out["employment_type"] == "full_time"
    assert out["posted_date"] is not None

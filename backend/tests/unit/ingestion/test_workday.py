from __future__ import annotations

import pytest

from hiresense.ingestion.adapters import WorkdayAdapter
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import WorkdayNormalizer
from hiresense.ingestion.domain.portal_config import PortalEntry
from hiresense.kernel.value_objects import SourceType


class FakeResponse:
    def __init__(self, data: dict, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        if not self.is_success:
            raise RuntimeError(f"status {self.status_code}")


class FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("POST", url))
        return FakeResponse(
            {
                "total": 1,
                "jobPostings": [
                    {
                        "title": "Senior Platform Engineer",
                        "externalPath": "JR-123",
                        "locationsText": "Mexico City, Mexico",
                        "postedOn": "2026-07-01",
                    }
                ],
            }
        )

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("GET", url))
        return FakeResponse(
            {
                "jobPostingInfo": {
                    "jobDescription": "<p>Build APIs at scale</p>",
                    "externalUrl": "https://example.myworkdayjobs.com/en-US/Careers/job/JR-123",
                    "jobFamily": "Engineering",
                }
            }
        )


@pytest.mark.asyncio
async def test_workday_fetches_jobs_from_portal_url() -> None:
    client = FakeHttpClient()
    adapter = WorkdayAdapter(http_client=client, timeout=10.0)
    portal = PortalEntry(
        name="Acme",
        platform="workday",
        board_id="https://example.myworkdayjobs.com/en-US/Careers/jobs",
        careers_url="https://example.myworkdayjobs.com/en-US/Careers/jobs",
    )
    jobs = await adapter.fetch_portal(portal)
    assert len(jobs) == 1
    assert jobs[0].source == "workday"
    assert jobs[0].source_id == "JR-123"
    assert jobs[0].raw_data["company"] == "Acme"
    assert client.calls[0] == (
        "POST",
        "https://example.myworkdayjobs.com/wday/cxs/en-US/Careers/jobs",
    )


def test_workday_source_metadata() -> None:
    adapter = WorkdayAdapter(http_client=None, timeout=10.0)
    assert adapter.source_name() == "workday"
    assert adapter.source_type() == SourceType.API
    assert adapter.supports_snapshot_closure() is True


def test_workday_normalizer_uses_detail_payload() -> None:
    raw = RawJobListing(
        source="workday",
        source_id="JR-123",
        raw_data={
            "title": "Senior Platform Engineer",
            "company": "Acme",
            "locationsText": "Mexico City, Mexico",
            "postedOn": "2026-07-01",
            "careers_url": "https://example.myworkdayjobs.com/en-US/Careers/jobs",
            "detail": {
                "jobPostingInfo": {
                    "jobDescription": "<p>Build APIs at scale</p>",
                    "externalUrl": "https://example.myworkdayjobs.com/en-US/Careers/job/JR-123",
                    "jobFamily": "Engineering",
                }
            },
        },
    )
    result = WorkdayNormalizer().normalize(raw)
    assert result["title"] == "Senior Platform Engineer"
    assert result["company"] == "Acme"
    assert "Build APIs at scale" in result["description"]
    assert result["location"] == "Mexico City, Mexico"
    assert result["department"] == "Engineering"

from __future__ import annotations

import pytest

from hiresense.ingestion.adapters import GlobantAdapter, ThoughtworksAdapter
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import GlobantNormalizer, ThoughtworksNormalizer
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


class FakeThoughtworksClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(url)
        return FakeResponse(
            {
                "jobs": [
                    {
                        "sourceSystemId": "8042982",
                        "name": "Platform Engineer",
                        "location": "Santiago",
                        "country": "Chile",
                        "remoteEligible": True,
                        "jobFunctions": ["Technology"],
                        "updatedAt": "2026-07-01",
                    }
                ]
            }
        )


class FakeGlobantClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url: str, **kwargs) -> FakeResponse:
        params = kwargs.get("params") or {}
        self.calls.append((url, params))
        page = int(params.get("page") or 1)
        if page == 1:
            return FakeResponse(
                {
                    "jobRequisition": [
                        {
                            "jobReqId": "78869",
                            "jobTitle": "Python Developer",
                            "location": "Buenos Aires, Argentina",
                            "country": "Argentina",
                            "jobDescription": "<p>Build APIs</p>",
                            "createdDateTime": "2026-07-21T14:25:16.000Z",
                            "area": [{"label": "Engineering"}],
                        }
                    ],
                    "showMore": True,
                    "totalPages": 2,
                    "total": 2,
                }
            )
        return FakeResponse(
            {
                "jobRequisition": [
                    {
                        "jobReqId": "78840",
                        "jobTitle": "Data Engineer",
                        "location": "Mexico City, Mexico",
                        "country": "Mexico",
                        "jobDescription": "<p>Pipelines</p>",
                        "createdDateTime": "2026-07-20T10:00:00.000Z",
                        "area": [{"label": "Data"}],
                    }
                ],
                "showMore": False,
                "totalPages": 2,
                "total": 2,
            }
        )


THOUGHTWORKS_URL = "https://tw.test/rest/careers/jobs"
GLOBANT_URL = "https://globant.test/api/sap/job-requisition"


@pytest.mark.asyncio
async def test_thoughtworks_fetches_jobs() -> None:
    client = FakeThoughtworksClient()
    adapter = ThoughtworksAdapter(http_client=client, base_url=THOUGHTWORKS_URL, timeout=10.0)
    portal = PortalEntry(
        name="Thoughtworks",
        platform="thoughtworks",
        board_id="thoughtworks",
        careers_url="https://www.thoughtworks.com/careers",
    )
    jobs = await adapter.fetch_portal(portal)
    assert len(jobs) == 1
    assert jobs[0].source_id == "8042982"
    assert jobs[0].raw_data["company"] == "Thoughtworks"
    assert adapter.source_type() == SourceType.API
    assert client.calls == [THOUGHTWORKS_URL]


def test_thoughtworks_normalizer() -> None:
    raw = RawJobListing(
        source="thoughtworks",
        source_id="8042982",
        raw_data={
            "sourceSystemId": "8042982",
            "name": "Platform Engineer",
            "location": "Santiago",
            "country": "Chile",
            "remoteEligible": True,
            "jobFunctions": ["Technology"],
            "company": "Thoughtworks",
        },
    )
    normalized = ThoughtworksNormalizer().normalize(raw)
    assert normalized["title"] == "Platform Engineer"
    assert "Remote" in normalized["location"]
    assert normalized["url"].endswith("/8042982")


@pytest.mark.asyncio
async def test_globant_paginates_job_requisitions() -> None:
    client = FakeGlobantClient()
    adapter = GlobantAdapter(http_client=client, base_url=GLOBANT_URL, timeout=10.0)
    portal = PortalEntry(
        name="Globant",
        platform="globant",
        board_id="globant",
        careers_url="https://career.globant.com/",
    )
    jobs = await adapter.fetch_portal(portal)
    assert len(jobs) == 2
    assert {j.source_id for j in jobs} == {"78869", "78840"}
    assert len(client.calls) == 2
    assert [url for url, _ in client.calls] == [GLOBANT_URL, GLOBANT_URL]


@pytest.mark.asyncio
async def test_globant_strips_trailing_query_marker_from_configured_url() -> None:
    """Operators may paste the URL with a trailing '?'; params are appended."""
    client = FakeGlobantClient()
    adapter = GlobantAdapter(http_client=client, base_url=f"{GLOBANT_URL}?", timeout=10.0)

    await adapter.fetch_jobs(board_id="globant", company_name="Globant")

    assert [url for url, _ in client.calls] == [GLOBANT_URL, GLOBANT_URL]
    assert [params["page"] for _, params in client.calls] == [1, 2]


def test_globant_normalizer() -> None:
    raw = RawJobListing(
        source="globant",
        source_id="78869",
        raw_data={
            "jobReqId": "78869",
            "jobTitle": "Python Developer",
            "location": "Buenos Aires, Argentina",
            "country": "Argentina",
            "jobDescription": "<p>Build APIs</p>",
            "company": "Globant",
            "area": [{"label": "Engineering"}],
        },
    )
    normalized = GlobantNormalizer().normalize(raw)
    assert normalized["title"] == "Python Developer"
    assert normalized["department"] == "Engineering"
    assert normalized["url"] == "https://career.globant.com/?id=78869"

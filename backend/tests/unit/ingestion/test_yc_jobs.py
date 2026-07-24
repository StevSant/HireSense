from __future__ import annotations

import html
import json

import pytest

from hiresense.ingestion.adapters.yc_jobs import YCJobsAdapter, extract_inertia_props
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import YCJobsNormalizer
from hiresense.kernel.value_objects import SourceType


def _page(jobs: list[dict], *, company: dict | None = None) -> str:
    if company is not None:
        props = {"company": company, "nav": {}, "flash": {}}
        component = "jobs/public/pages/CompanyPage"
    else:
        props = {"jobs": jobs, "nav": {}, "flash": {}, "roleLinks": []}
        component = "jobs/public/pages/JobsPage"
    payload = html.escape(json.dumps({"component": component, "props": props}))
    return f'<html><body><div data-page="{payload}"></div></body></html>'


SAMPLE_JOB = {
    "id": 92753,
    "title": "Senior Software Engineer",
    "jobType": "Fulltime",
    "location": "United States - Remote / Remote (US)",
    "roleType": "Full stack",
    "salary": "$180K - $220K",
    "companyName": "OneSignal",
    "companySlug": "onesignal",
    "companyBatch": "S11",
    "companyOneLiner": "Messaging platform",
    "applyUrl": "https://account.ycombinator.com/authenticate?continue=x",
}


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttpClient:
    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping
        self.calls: list[str] = []

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(url)
        for needle, body in self._mapping.items():
            if needle in url:
                return FakeResponse(body)
        return FakeResponse("missing", status_code=404)


def test_extract_inertia_props() -> None:
    props = extract_inertia_props(_page([SAMPLE_JOB]))
    assert len(props["jobs"]) == 1


@pytest.mark.asyncio
async def test_yc_fetches_roles() -> None:
    client = FakeHttpClient(
        {
            "/jobs/role/software-engineer": _page([SAMPLE_JOB]),
            "/jobs/role/product": _page([]),
        }
    )
    adapter = YCJobsAdapter(
        http_client=client,
        roles=["software-engineer", "product"],
        enrich_companies=False,
    )
    jobs = await adapter.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].source_id == "92753"
    assert adapter.source_type() == SourceType.SCRAPER
    assert adapter.supports_snapshot_closure() is False


@pytest.mark.asyncio
async def test_yc_company_enrichment() -> None:
    company = {
        "name": "OneSignal",
        "slug": "onesignal",
        "batch": "S11",
        "teamSize": 200,
        "industry": "B2B",
        "jobs": [
            {
                "id": 92753,
                "title": "Senior Software Engineer",
                "location": "Remote (US)",
                "jobType": "Full-time",
                "salaryRange": "$180K - $220K",
                "equityRange": "0.01% – 0.05%",
                "sponsorsVisa": True,
                "minExperience": 5,
            }
        ],
    }
    client = FakeHttpClient(
        {
            "/jobs/role/software-engineer": _page([SAMPLE_JOB]),
            "/companies/onesignal": _page([], company=company),
        }
    )
    adapter = YCJobsAdapter(
        http_client=client,
        roles=["software-engineer"],
        enrich_companies=True,
        company_enrich_limit=5,
    )
    jobs = await adapter.fetch_jobs()
    assert jobs[0].raw_data["equityRange"] == "0.01% – 0.05%"
    assert jobs[0].raw_data["sponsorsVisa"] is True


@pytest.mark.asyncio
async def test_yc_parse_failure_isolated() -> None:
    client = FakeHttpClient({"/jobs/role/software-engineer": "<html>no data</html>"})
    adapter = YCJobsAdapter(http_client=client, roles=["software-engineer"], enrich_companies=False)
    assert await adapter.fetch_jobs() == []
    assert adapter.last_parse_failures >= 1


def test_yc_normalizer() -> None:
    raw = RawJobListing(
        source="yc_jobs",
        source_id="92753",
        raw_data={
            **SAMPLE_JOB,
            "equityRange": "0.1% – 0.25%",
            "sponsorsVisa": "US citizen/visa only",
            "_company": {"teamSize": 50, "industry": "Fintech"},
        },
    )
    out = YCJobsNormalizer().normalize(raw)
    assert out["company"] == "OneSignal"
    assert out["salary_range"] == "$180K - $220K"
    assert out["equity_range"] == "0.1% – 0.25%"
    assert out["employment_type"] == "full_time"
    assert out["remote_modality"] == "remote"
    assert out["source_metadata"]["yc_batch"] == "S11"
    assert out["source_metadata"]["team_size"] == 50
    assert "Full stack" in out["skills"]

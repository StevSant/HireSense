from __future__ import annotations

import asyncio

import pytest

from hiresense.ingestion.adapters import GetOnBoardAdapter
from hiresense.ingestion.domain.normalizers import GetOnBoardNormalizer


class FakeResponse:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.status_code = 200

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        pass


class FakeHttpClient:
    """Returns the jobs page for any non-company URL and a company resource for
    /companies/{id}. Records every fetched URL so we can assert caching."""

    def __init__(self, jobs_page: dict, company_names: dict[str, str]) -> None:
        self._jobs_page = jobs_page
        self._company_names = company_names
        self.calls: list[str] = []

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(url)
        if "/companies/" in url:
            cid = url.rsplit("/", 1)[1]
            return FakeResponse(
                {"data": {"id": cid, "attributes": {"name": self._company_names.get(cid, "")}}}
            )
        return FakeResponse(self._jobs_page)


def _jobs_page(*company_ids: int) -> dict:
    return {
        "data": [
            {
                "id": f"job-{cid}",
                "type": "job",
                "attributes": {
                    "title": "Dev",
                    "company": {"data": {"id": cid, "type": "company"}},
                    "remote": True,
                    "remote_modality": "remote_local",
                    "countries": [],
                    "description": "desc",
                },
                "links": {"public_url": f"https://www.getonbrd.com/jobs/job-{cid}"},
                "relationships": {"tags": {"data": []}},
            }
            for cid in company_ids
        ],
        "meta": {"total_pages": 1},
    }


@pytest.mark.asyncio
async def test_getonboard_resolves_company_name_into_attributes() -> None:
    http = FakeHttpClient(_jobs_page(9458), {"9458": "BC Tecnología"})
    adapter = GetOnBoardAdapter(http_client=http, base_url="https://api", categories=None)

    jobs = await adapter.fetch_jobs()

    assert jobs[0].raw_data["attributes"]["company_name"] == "BC Tecnología"
    # The normalizer must then surface the resolved name as the company.
    out = GetOnBoardNormalizer().normalize(jobs[0])
    assert out["company"] == "BC Tecnología"


@pytest.mark.asyncio
async def test_getonboard_caches_company_lookups() -> None:
    # Two jobs share a company id → only one /companies fetch.
    http = FakeHttpClient(_jobs_page(9458, 9458), {"9458": "BC Tecnología"})
    adapter = GetOnBoardAdapter(http_client=http, base_url="https://api", categories=None)

    await adapter.fetch_jobs()

    company_calls = [u for u in http.calls if "/companies/" in u]
    assert company_calls == ["https://api/companies/9458"]


@pytest.mark.asyncio
async def test_getonboard_company_unresolved_leaves_blank() -> None:
    # Company fetch yields no name → no company_name injected; normalizer blank.
    http = FakeHttpClient(_jobs_page(123), {})  # 123 not in name map
    adapter = GetOnBoardAdapter(http_client=http, base_url="https://api", categories=None)

    jobs = await adapter.fetch_jobs()

    assert "company_name" not in jobs[0].raw_data["attributes"]
    out = GetOnBoardNormalizer().normalize(jobs[0])
    assert out["company"] == ""


class _ConcurrencyTrackingClient:
    """Records the peak number of concurrent /companies/{id} calls in flight."""

    def __init__(self, jobs_page: dict, company_names: dict[str, str]) -> None:
        self._jobs_page = jobs_page
        self._company_names = company_names
        self.inflight = 0
        self.max_inflight = 0
        self.company_calls = 0

    async def get(self, url: str, **kwargs) -> FakeResponse:
        if "/companies/" not in url:
            return FakeResponse(self._jobs_page)
        self.company_calls += 1
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        try:
            await asyncio.sleep(0.02)  # hold the slot so overlap is observable
        finally:
            self.inflight -= 1
        cid = url.rsplit("/", 1)[1]
        return FakeResponse(
            {"data": {"id": cid, "attributes": {"name": self._company_names.get(cid, "")}}}
        )


@pytest.mark.asyncio
async def test_getonboard_resolves_companies_concurrently_within_bound() -> None:
    names = {str(cid): f"Company {cid}" for cid in (1, 2, 3, 4)}
    http = _ConcurrencyTrackingClient(_jobs_page(1, 2, 3, 4), names)
    adapter = GetOnBoardAdapter(
        http_client=http, base_url="https://api", categories=None, company_concurrency=2
    )

    jobs = await adapter.fetch_jobs()

    # One round-trip per DISTINCT company, run in parallel but capped at 2.
    assert http.company_calls == 4
    assert http.max_inflight == 2  # concurrent (>1) yet never above the bound
    assert {j.raw_data["attributes"]["company_name"] for j in jobs} == set(names.values())

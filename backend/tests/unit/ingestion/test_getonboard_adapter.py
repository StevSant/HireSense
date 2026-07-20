from __future__ import annotations

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


class _RichCompanyHttpClient:
    """Returns a full company profile for /companies/{id} so the adapter has
    description/long_description/web/country to capture."""

    def __init__(self, jobs_page: dict, attributes: dict) -> None:
        self._jobs_page = jobs_page
        self._attributes = attributes

    async def get(self, url: str, **kwargs) -> FakeResponse:
        if "/companies/" in url:
            cid = url.rsplit("/", 1)[1]
            return FakeResponse({"data": {"id": cid, "attributes": self._attributes}})
        return FakeResponse(self._jobs_page)


class _RecordingSink:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


@pytest.mark.asyncio
async def test_getonboard_captures_company_profile_to_sink() -> None:
    attributes = {
        "name": "BC Tecnología",
        "description": "Somos una consultora de TI.",
        "long_description": "<p>Más de 6 años de experiencia.</p>",
        "web": "https://bctecnologia.cl",
        "country": "Chile",
    }
    sink = _RecordingSink()
    adapter = GetOnBoardAdapter(
        http_client=_RichCompanyHttpClient(_jobs_page(9458), attributes),
        base_url="https://api",
        categories=None,
        profile_sink=sink,
    )

    await adapter.fetch_jobs()

    assert len(sink.records) == 1
    record = sink.records[0]
    assert record["company_name"] == "BC Tecnología"
    assert record["source"] == "getonboard"
    assert record["website"] == "https://bctecnologia.cl"
    assert record["headquarters"] == "Chile"
    # Short + stripped long description, plain text (no HTML tags).
    assert "Somos una consultora de TI." in record["description"]
    assert "Más de 6 años de experiencia." in record["description"]
    assert "<p>" not in record["description"]


@pytest.mark.asyncio
async def test_getonboard_profile_capture_respects_char_limit() -> None:
    attributes = {"name": "BC", "description": "x" * 5000}
    sink = _RecordingSink()
    adapter = GetOnBoardAdapter(
        http_client=_RichCompanyHttpClient(_jobs_page(9458), attributes),
        base_url="https://api",
        categories=None,
        profile_sink=sink,
        profile_char_limit=100,
    )

    await adapter.fetch_jobs()

    # Truncated to the limit (+ the single ellipsis marker).
    assert len(sink.records[0]["description"]) <= 101


@pytest.mark.asyncio
async def test_getonboard_without_sink_still_resolves_name() -> None:
    # No profile_sink wired → capture is a no-op, name resolution unaffected.
    http = FakeHttpClient(_jobs_page(9458), {"9458": "BC Tecnología"})
    adapter = GetOnBoardAdapter(http_client=http, base_url="https://api", categories=None)

    jobs = await adapter.fetch_jobs()

    assert jobs[0].raw_data["attributes"]["company_name"] == "BC Tecnología"

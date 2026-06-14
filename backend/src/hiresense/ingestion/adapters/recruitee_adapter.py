from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class RecruiteeAdapter:
    """Recruitee public Offers API.

    ``GET {base_url}/offers/`` (where base_url is templated with the company
    subdomain) returns every published offer in one call, with full description
    and inline salary — a complete snapshot of the company's open roles.
    ``board_id`` is the company subdomain; ``base_url`` must contain a
    ``{company}`` placeholder (e.g. ``https://{company}.recruitee.com/api``).
    """

    def __init__(self, http_client: Any, base_url: str, timeout: float) -> None:
        self._http = http_client
        self._base_url = base_url
        self._timeout = timeout

    def supports_snapshot_closure(self) -> bool:
        return True

    def source_name(self) -> str:
        return "recruitee"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, board_id: str, company_name: str) -> list[RawJobListing]:
        base = self._base_url.format(company=board_id)
        url = f"{base}/offers/"
        response = await self._http.get(url, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()
        return [
            RawJobListing(
                source="recruitee",
                source_id=str(offer["id"]),
                raw_data={**offer, "company": company_name},
            )
            for offer in data.get("offers", [])
            if offer.get("id") is not None
        ]

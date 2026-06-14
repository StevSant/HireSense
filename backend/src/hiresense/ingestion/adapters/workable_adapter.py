from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class WorkableAdapter:
    """Workable public job-board widget API.

    ``GET {base_url}/{board_id}?details=true`` returns the account's COMPLETE
    set of published jobs in one call (``{"jobs": [...]}``), so it supports
    snapshot closure. ``board_id`` is the account subdomain. ``?details=true``
    asks Workable to inline the description/requirements/benefits HTML.
    """

    def __init__(self, http_client: Any, base_url: str, timeout: float) -> None:
        self._http = http_client
        self._base_url = base_url
        self._timeout = timeout

    def supports_snapshot_closure(self) -> bool:
        return True

    def source_name(self) -> str:
        return "workable"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, board_id: str, company_name: str) -> list[RawJobListing]:
        url = f"{self._base_url}/{board_id}"
        response = await self._http.get(
            url, params={"details": "true"}, timeout=self._timeout
        )
        response.raise_for_status()
        data = response.json()
        return [
            RawJobListing(
                source="workable",
                source_id=str(job.get("shortcode") or job.get("id") or ""),
                raw_data={**job, "company": company_name},
            )
            for job in data.get("jobs", [])
            if job.get("shortcode") or job.get("id")
        ]

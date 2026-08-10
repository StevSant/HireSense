from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.portal_config import PortalEntry
from hiresense.kernel.value_objects import SourceType


class ThoughtworksAdapter:
    """Thoughtworks public careers JSON feed.

    ``GET https://www.thoughtworks.com/rest/careers/jobs`` returns the complete
    open set in one call, so it supports snapshot closure.
    """

    def __init__(self, http_client: Any, base_url: str, timeout: float) -> None:
        self._http = http_client
        self._base_url = base_url
        self._timeout = timeout

    def supports_snapshot_closure(self) -> bool:
        return True

    def source_name(self) -> str:
        return "thoughtworks"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_portal(self, portal: PortalEntry) -> list[RawJobListing]:
        response = await self._http.get(self._base_url, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            return []
        results: list[RawJobListing] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            source_id = str(job.get("sourceSystemId") or job.get("name") or "").strip()
            if not source_id:
                continue
            results.append(
                RawJobListing(
                    source="thoughtworks",
                    source_id=source_id,
                    raw_data={**job, "company": portal.name},
                )
            )
        return results

    async def fetch_jobs(self, board_id: str, company_name: str) -> list[RawJobListing]:
        portal = PortalEntry(name=company_name, platform="auto", board_id=board_id)
        return await self.fetch_portal(portal)

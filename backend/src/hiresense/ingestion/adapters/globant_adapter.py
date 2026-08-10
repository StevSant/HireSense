from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.portal_config import PortalEntry
from hiresense.shared.kernel.value_objects import SourceType


class GlobantAdapter:
    """Globant SuccessFactors careers API (Next.js BFF).

    ``GET https://career.globant.com/api/sap/job-requisition?page=N`` returns a
    paginated snapshot (``showMore`` / ``totalPages``), so this source supports
    snapshot closure.
    """

    def __init__(
        self,
        http_client: Any,
        base_url: str,
        timeout: float,
        *,
        max_pages: int = 50,
    ) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("?")
        self._timeout = timeout
        self._max_pages = max_pages

    def supports_snapshot_closure(self) -> bool:
        return True

    def source_name(self) -> str:
        return "globant"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_portal(self, portal: PortalEntry) -> list[RawJobListing]:
        results: list[RawJobListing] = []
        seen: set[str] = set()
        page = 1
        while page <= self._max_pages:
            response = await self._http.get(
                self._base_url,
                params={"page": page},
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            jobs = data.get("jobRequisition") if isinstance(data, dict) else None
            if not isinstance(jobs, list) or not jobs:
                break
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                source_id = str(job.get("jobReqId") or "").strip()
                if not source_id or source_id in seen:
                    continue
                seen.add(source_id)
                results.append(
                    RawJobListing(
                        source="globant",
                        source_id=source_id,
                        raw_data={**job, "company": portal.name},
                    )
                )
            show_more = bool(data.get("showMore")) if isinstance(data, dict) else False
            total_pages = int(data.get("totalPages") or page) if isinstance(data, dict) else page
            if not show_more or page >= total_pages:
                break
            page += 1
        return results

    async def fetch_jobs(self, board_id: str, company_name: str) -> list[RawJobListing]:
        portal = PortalEntry(name=company_name, platform="auto", board_id=board_id)
        return await self.fetch_portal(portal)

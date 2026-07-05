from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

MAX_PAGES = 3


class ArbeitnowAdapter:
    """Arbeitnow free Job Board API (Europe + remote, no auth).

    ``GET {base_url}?page=N`` returns a page of jobs under ``data`` with
    ``links.next`` for pagination. A feed source (not a complete snapshot), so
    closure is handled by the URL-probe revalidation sweep.
    """

    def __init__(self, http_client: Any, base_url: str) -> None:
        self._http = http_client
        self._base_url = base_url

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "arbeitnow"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
        search = filters.get("search", "") if filters else ""
        jobs: list[RawJobListing] = []
        seen: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            params: dict[str, str] = {"page": str(page)}
            if search:
                params["search"] = search
            response = await self._http.get(self._base_url, params=params)
            response.raise_for_status()
            data = response.json()
            page_jobs = data.get("data", [])
            if not page_jobs:
                break
            for job in page_jobs:
                slug = job.get("slug", "")
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                jobs.append(RawJobListing(source="arbeitnow", source_id=slug, raw_data=job))
            if not data.get("links", {}).get("next"):
                break
        return jobs

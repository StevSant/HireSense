from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

MAX_PAGES = 10


class GetOnBoardAdapter:
    def __init__(self, http_client: Any, base_url: str) -> None:
        self._http = http_client
        self._base_url = base_url

    def source_name(self) -> str:
        return "getonboard"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        jobs: list[RawJobListing] = []
        page = 1
        query = filters.get("query", "") if filters else ""
        for _ in range(MAX_PAGES):
            params: dict[str, str] = {
                "per_page": "100",
                "page": str(page),
            }
            url = f"{self._base_url}/search/jobs"
            if query:
                params["query"] = query
            response = await self._http.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            page_data = data.get("data", [])
            if not page_data:
                break
            for item in page_data:
                jobs.append(
                    RawJobListing(
                        source="getonboard",
                        source_id=str(item.get("id", "")),
                        raw_data=item,
                    )
                )
            meta = data.get("meta", {})
            total_pages = meta.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
        return jobs

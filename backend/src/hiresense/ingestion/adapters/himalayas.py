from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

MAX_PAGES = 10
PAGE_LIMIT = 20


class HimalayasAdapter:
    def __init__(self, http_client: Any, base_url: str) -> None:
        self._http = http_client
        self._base_url = base_url

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "himalayas"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
        jobs: list[RawJobListing] = []
        offset = 0
        for _ in range(MAX_PAGES):
            params: dict[str, str] = {
                "offset": str(offset),
                "limit": str(PAGE_LIMIT),
            }
            response = await self._http.get(self._base_url, params=params)
            response.raise_for_status()
            data = response.json()
            page_jobs = data.get("jobs", [])
            if not page_jobs:
                break
            for job in page_jobs:
                guid = job.get("guid") or job.get("title", "")
                jobs.append(RawJobListing(source="himalayas", source_id=guid, raw_data=job))
            offset += PAGE_LIMIT
        return jobs

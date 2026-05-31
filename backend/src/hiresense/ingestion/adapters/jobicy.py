from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class JobicyAdapter:
    def __init__(self, http_client: Any, base_url: str) -> None:
        self._http = http_client
        self._base_url = base_url

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "jobicy"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        params: dict[str, str] = {"count": "50"}
        if filters:
            if "geo" in filters:
                params["geo"] = filters["geo"]
            if "industry" in filters:
                params["industry"] = filters["industry"]
            if "tag" in filters:
                params["tag"] = filters["tag"]
        response = await self._http.get(self._base_url, params=params)
        response.raise_for_status()
        data = response.json()
        return [
            RawJobListing(source="jobicy", source_id=str(job["id"]), raw_data=job)
            for job in data.get("jobs", [])
        ]

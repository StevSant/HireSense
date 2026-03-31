from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveAdapter:
    def __init__(self, http_client: Any) -> None:
        self._http = http_client

    def source_name(self) -> str:
        return "remotive"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        params: dict[str, str] = {}
        if filters and "category" in filters:
            params["category"] = filters["category"]
        if filters and "search" in filters:
            params["search"] = filters["search"]
        response = await self._http.get(REMOTIVE_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return [
            RawJobListing(source="remotive", source_id=str(job["id"]), raw_data=job)
            for job in data.get("jobs", [])
        ]

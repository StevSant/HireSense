from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class AshbyAdapter:
    def __init__(self, http_client: Any, base_url: str, timeout: float) -> None:
        self._http = http_client
        self._base_url = base_url
        self._timeout = timeout

    def source_name(self) -> str:
        return "ashby"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, board_id: str, company_name: str) -> list[RawJobListing]:
        url = f"{self._base_url}/{board_id}"
        response = await self._http.post(url)
        response.raise_for_status()
        data = response.json()
        return [
            RawJobListing(
                source="ashby",
                source_id=str(job["id"]),
                raw_data={**job, "company": company_name},
            )
            for job in data.get("jobs", [])
        ]

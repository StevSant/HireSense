from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class LeverAdapter:
    def __init__(self, http_client: Any, base_url: str, timeout: float) -> None:
        self._http = http_client
        self._base_url = base_url
        self._timeout = timeout

    def source_name(self) -> str:
        return "lever"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, board_id: str, company_name: str) -> list[RawJobListing]:
        url = f"{self._base_url}/{board_id}"
        response = await self._http.get(url, params={"mode": "json"}, timeout=self._timeout)
        response.raise_for_status()
        postings = response.json()
        return [
            RawJobListing(
                source="lever",
                source_id=str(posting["id"]),
                raw_data={**posting, "company": company_name},
            )
            for posting in postings
        ]

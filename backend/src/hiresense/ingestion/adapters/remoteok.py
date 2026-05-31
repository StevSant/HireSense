from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

REMOTEOK_API_URL = "https://remoteok.com/api"


class RemoteOKAdapter:
    def __init__(self, http_client: Any) -> None:
        self._http = http_client

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "remoteok"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        headers = {"User-Agent": "HireSense/1.0"}
        response = await self._http.get(REMOTEOK_API_URL, headers=headers)
        response.raise_for_status()
        data = response.json()
        jobs: list[RawJobListing] = []
        for item in data:
            if "id" not in item or "position" not in item:
                continue
            jobs.append(
                RawJobListing(
                    source="remoteok",
                    source_id=str(item["id"]),
                    raw_data=item,
                )
            )
        return jobs

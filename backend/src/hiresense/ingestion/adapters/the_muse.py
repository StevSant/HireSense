from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

MAX_PAGES = 3


class TheMuseAdapter:
    """The Muse public Jobs API (global, on-site + remote).

    ``GET {base_url}?page=N&category=...`` returns ``results`` (and a total
    ``page_count``). The board is broad — non-tech roles dominate — so the
    configured ``categories`` narrow it to dev-relevant listings. An API key is
    optional (higher rate limit); sent only when configured. A feed source, so
    closure is handled by the URL-probe revalidation sweep.
    """

    def __init__(
        self,
        http_client: Any,
        base_url: str,
        categories: list[str] | None = None,
        api_key: str = "",
    ) -> None:
        self._http = http_client
        self._base_url = base_url
        self._categories = list(categories) if categories else []
        self._api_key = api_key

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "themuse"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        jobs: list[RawJobListing] = []
        seen: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            params: list[tuple[str, str]] = [("page", str(page))]
            for category in self._categories:
                params.append(("category", category))
            if self._api_key:
                params.append(("api_key", self._api_key))
            response = await self._http.get(self._base_url, params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            if not results:
                break
            for job in results:
                source_id = str(job.get("id", ""))
                if not source_id or source_id in seen:
                    continue
                seen.add(source_id)
                jobs.append(
                    RawJobListing(source="themuse", source_id=source_id, raw_data=job)
                )
            if page >= data.get("page_count", 1):
                break
        return jobs

from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

MAX_PAGES = 10


class GetOnBoardAdapter:
    def __init__(
        self,
        http_client: Any,
        base_url: str,
        categories: list[str] | None = None,
    ) -> None:
        self._http = http_client
        self._base_url = base_url
        # Empty/None → ingest from /search/jobs with no filter.
        self._categories = list(categories) if categories else []

    def source_name(self) -> str:
        return "getonboard"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        query = filters.get("query", "") if filters else ""
        seen: set[str] = set()
        jobs: list[RawJobListing] = []
        # A free-text query overrides category iteration; otherwise iterate
        # across the configured categories so the listing matches the breadth
        # of getonbrd.com (which is multi-category, not just programming).
        if query:
            await self._fetch_endpoint(
                f"{self._base_url}/search/jobs",
                extra_params={"query": query},
                seen=seen,
                jobs=jobs,
            )
        elif self._categories:
            for category in self._categories:
                await self._fetch_endpoint(
                    f"{self._base_url}/categories/{category}/jobs",
                    extra_params={},
                    seen=seen,
                    jobs=jobs,
                )
        else:
            await self._fetch_endpoint(
                f"{self._base_url}/search/jobs",
                extra_params={},
                seen=seen,
                jobs=jobs,
            )
        return jobs

    async def _fetch_endpoint(
        self,
        url: str,
        extra_params: dict[str, str],
        seen: set[str],
        jobs: list[RawJobListing],
    ) -> None:
        for page in range(1, MAX_PAGES + 1):
            params: dict[str, str] = {"per_page": "100", "page": str(page), **extra_params}
            response = await self._http.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            page_data = data.get("data", [])
            if not page_data:
                return
            for item in page_data:
                source_id = str(item.get("id", ""))
                if not source_id or source_id in seen:
                    continue
                seen.add(source_id)
                jobs.append(
                    RawJobListing(
                        source="getonboard",
                        source_id=source_id,
                        raw_data=item,
                    )
                )
            meta = data.get("meta", {})
            if page >= meta.get("total_pages", 1):
                return

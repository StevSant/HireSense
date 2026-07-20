from __future__ import annotations

import asyncio
import logging
from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

logger = logging.getLogger(__name__)

MAX_PAGES = 10


class GetOnBoardAdapter:
    def __init__(
        self,
        http_client: Any,
        base_url: str,
        categories: list[str] | None = None,
        company_concurrency: int = 8,
    ) -> None:
        self._http = http_client
        self._base_url = base_url
        # Empty/None → ingest from /search/jobs with no filter.
        self._categories = list(categories) if categories else []
        # company id → name, resolved lazily and reused across the run so we
        # never fetch the same company twice (see _resolve_company_names).
        self._company_cache: dict[str, str] = {}
        self._company_concurrency = max(1, company_concurrency)

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "getonboard"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
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
        await self._resolve_company_names(jobs)
        return jobs

    async def _resolve_company_names(self, jobs: list[RawJobListing]) -> None:
        """Inject the human-readable company name into each job's attributes.

        getonbrd's job listings carry only a company *id*
        (``attributes.company.data.id``), not the name, so without this the
        company column renders blank. We resolve the DISTINCT ids concurrently
        via ``/companies/{id}`` under a bounded semaphore (one round-trip per
        distinct company instead of a serial loop over every job), cache the
        results, and stash each name under ``attributes.company_name``, which
        the normalizer already reads. Failures degrade to a blank company rather
        than breaking the whole fetch.
        """
        # Distinct, resolution-order-preserving ids still needing a name.
        pending: dict[str, None] = {}
        for raw in jobs:
            attrs = raw.raw_data.get("attributes", {})
            if attrs.get("company_name"):
                continue
            company_id = (attrs.get("company") or {}).get("data", {}).get("id")
            if company_id is not None:
                pending.setdefault(str(company_id), None)
        if not pending:
            return

        sem = asyncio.Semaphore(self._company_concurrency)

        async def _resolve(company_id: str) -> tuple[str, str]:
            async with sem:
                return company_id, await self._company_name(company_id)

        resolved = dict(await asyncio.gather(*(_resolve(cid) for cid in pending)))

        for raw in jobs:
            attrs = raw.raw_data.get("attributes", {})
            if attrs.get("company_name"):
                continue
            company_id = (attrs.get("company") or {}).get("data", {}).get("id")
            if company_id is None:
                continue
            name = resolved.get(str(company_id))
            if name:
                attrs["company_name"] = name

    async def _company_name(self, company_id: str) -> str:
        if company_id in self._company_cache:
            return self._company_cache[company_id]
        name = ""
        try:
            response = await self._http.get(f"{self._base_url}/companies/{company_id}")
            response.raise_for_status()
            data = response.json().get("data", {}) or {}
            name = ((data.get("attributes") or {}).get("name") or "").strip()
        except Exception:
            logger.warning("getonboard: failed to resolve company %s", company_id, exc_info=True)
        self._company_cache[company_id] = name
        return name

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

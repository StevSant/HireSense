from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

RESULTS_PER_PAGE = 50
MAX_PAGES = 3


class AdzunaAdapter:
    """Adzuna aggregator API (global, on-site/hybrid + salary data).

    ``GET {base_url}/{country}/search/{page}`` requires a free ``app_id`` +
    ``app_key``. Iterates the configured countries (LATAM-leaning by default).
    A feed/aggregator source, so closure is handled by the URL-probe sweep.
    The country code is injected into each job so the normalizer can attach the
    right salary currency.
    """

    def __init__(
        self,
        http_client: Any,
        base_url: str,
        app_id: str,
        app_key: str,
        countries: list[str] | None = None,
        query: str = "software developer",
    ) -> None:
        self._http = http_client
        self._base_url = base_url
        self._app_id = app_id
        self._app_key = app_key
        self._countries = list(countries) if countries else []
        self._query = query

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "adzuna"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        query = filters.get("query", self._query) if filters else self._query
        jobs: list[RawJobListing] = []
        for country in self._countries:
            for page in range(1, MAX_PAGES + 1):
                url = f"{self._base_url}/{country}/search/{page}"
                params = {
                    "app_id": self._app_id,
                    "app_key": self._app_key,
                    "results_per_page": str(RESULTS_PER_PAGE),
                    "what": query,
                    "content-type": "application/json",
                }
                response = await self._http.get(url, params=params)
                response.raise_for_status()
                results = response.json().get("results", [])
                if not results:
                    break
                for job in results:
                    job_id = str(job.get("id", ""))
                    if not job_id:
                        continue
                    jobs.append(
                        RawJobListing(
                            source="adzuna",
                            source_id=f"{country}-{job_id}",
                            raw_data={**job, "country": country},
                        )
                    )
                if len(results) < RESULTS_PER_PAGE:
                    break
        return jobs

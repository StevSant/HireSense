from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

PAGE_SIZE = 100
MAX_PAGES = 20


class SmartRecruitersAdapter:
    """SmartRecruiters public Posting API.

    ``GET {base_url}/{board_id}/postings`` lists every public posting for a
    company (paginated via ``offset``/``limit``), so across all pages it is a
    complete snapshot of the company's open roles. ``board_id`` is the company
    identifier. The listing carries metadata only — the public ad URL is built
    as ``jobs.smartrecruiters.com/{board_id}/{posting_id}``.
    """

    def __init__(self, http_client: Any, base_url: str, timeout: float) -> None:
        self._http = http_client
        self._base_url = base_url
        self._timeout = timeout

    def supports_snapshot_closure(self) -> bool:
        return True

    def source_name(self) -> str:
        return "smartrecruiters"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, board_id: str, company_name: str) -> list[RawJobListing]:
        url = f"{self._base_url}/{board_id}/postings"
        jobs: list[RawJobListing] = []
        offset = 0
        for _ in range(MAX_PAGES):
            response = await self._http.get(
                url,
                params={"offset": str(offset), "limit": str(PAGE_SIZE)},
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("content", [])
            if not content:
                break
            for job in content:
                job_id = str(job.get("id", ""))
                if not job_id:
                    continue
                public_url = f"https://jobs.smartrecruiters.com/{board_id}/{job_id}"
                jobs.append(
                    RawJobListing(
                        source="smartrecruiters",
                        source_id=job_id,
                        raw_data={**job, "company": company_name, "public_url": public_url},
                    )
                )
            offset += PAGE_SIZE
            if offset >= data.get("totalFound", 0):
                break
        return jobs

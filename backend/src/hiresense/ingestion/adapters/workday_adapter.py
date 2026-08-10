from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.portal_config import PortalEntry
from hiresense.shared.kernel.value_objects import SourceType


class WorkdayAdapter:
    """Workday public recruiting API.

    Accepts either a full careers URL in ``PortalEntry.careers_url`` or a full
    jobs endpoint/base URL in ``board_id``. It fetches the paginated job list
    and then enriches each row with the public detail payload when available.
    """

    def __init__(self, http_client: Any, timeout: float) -> None:
        self._http = http_client
        self._timeout = timeout

    def supports_snapshot_closure(self) -> bool:
        return True

    def source_name(self) -> str:
        return "workday"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_portal(self, portal: PortalEntry) -> list[RawJobListing]:
        list_url = self._jobs_endpoint(portal)
        payload = {"limit": 20, "offset": 0, "searchText": ""}
        response = await self._http.post(list_url, json=payload, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()
        postings = list(data.get("jobPostings") or [])
        total = int(data.get("total") or len(postings))
        offset = len(postings)

        while offset < total and postings:
            response = await self._http.post(
                list_url,
                json={"limit": 20, "offset": offset, "searchText": ""},
                timeout=self._timeout,
            )
            response.raise_for_status()
            page = response.json()
            next_postings = list(page.get("jobPostings") or [])
            if not next_postings:
                break
            postings.extend(next_postings)
            offset += len(next_postings)

        detail_base = list_url.rsplit("/jobs", 1)[0]
        results: list[RawJobListing] = []
        for job in postings:
            source_id = str(job.get("bulletFields", [None])[0] or job.get("title") or "").strip()
            external_path = str(job.get("externalPath") or "").strip()
            detail = None
            if external_path:
                detail_url = f"{detail_base}/job/{external_path}"
                detail_resp = await self._http.get(detail_url, timeout=self._timeout)
                if detail_resp.is_success:
                    detail = detail_resp.json()
            results.append(
                RawJobListing(
                    source="workday",
                    source_id=external_path or source_id,
                    raw_data={
                        **job,
                        "company": portal.name,
                        "detail": detail,
                        "careers_url": portal.careers_url,
                    },
                )
            )
        return results

    def _jobs_endpoint(self, portal: PortalEntry) -> str:
        candidate = (portal.careers_url or portal.board_id).strip()
        if not candidate:
            raise ValueError(f"Workday portal {portal.name} is missing careers_url/board_id")
        parsed = urlparse(candidate)
        if parsed.scheme and parsed.netloc:
            parts = [p for p in parsed.path.split("/") if p]
            if parts[:2] == ["wday", "cxs"]:
                return candidate
            if "jobs" in parts:
                jobs_idx = parts.index("jobs")
                if jobs_idx >= 2:
                    tenant = parts[jobs_idx - 2]
                    site = parts[jobs_idx - 1]
                    return f"{parsed.scheme}://{parsed.netloc}/wday/cxs/{tenant}/{site}/jobs"
            raise ValueError(f"Unsupported Workday careers URL for {portal.name}: {candidate}")
        return candidate

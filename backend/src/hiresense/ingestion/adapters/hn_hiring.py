from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

# The monthly HN ritual runs several parallel threads — "Who is hiring?"
# (companies), "Who wants to be hired?" (job seekers), and "Freelancer?
# Seeking freelancer?". People routinely cross-post a seeker pitch into the
# hiring thread; those comments lead with one of these markers instead of a
# company name. They are not job postings, so we drop them at ingestion.
_SEEKER_HEADER_PREFIXES = (
    "SEEKING WORK",
    "SEEKING FREELANCER",
    "SEEKING FULL-TIME",
    "SEEKING FULL TIME",
    "SEEKING PART-TIME",
    "SEEKING PART TIME",
    "SEEKING CONTRACT",
    "SEEKING POSITION",
    "SEEKING REMOTE",
)


def _is_seeker_post(text: str) -> bool:
    """True if the comment is a job-seeker pitch rather than a job posting.

    Seeker comments open their pipe-delimited header with a ``SEEKING …``
    marker (e.g. ``SEEKING WORK | Full-Stack Developer``), whereas company
    posts lead with the company name.
    """
    plain = strip_html(text)
    header = plain.split("\n", 1)[0]
    first_part = header.split("|", 1)[0].strip().upper()
    return first_part.startswith(_SEEKER_HEADER_PREFIXES)


class HNHiringAdapter:
    def __init__(self, http_client: Any, base_url: str) -> None:
        self._http = http_client
        self._base_url = base_url

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "hn_hiring"

    def source_type(self) -> SourceType:
        return SourceType.SCRAPER

    async def _find_latest_thread(self) -> str | None:
        url = f"{self._base_url}/search_by_date"
        params = {
            "query": '"Ask HN: Who is hiring"',
            "tags": "story",
            "hitsPerPage": "1",
        }
        response = await self._http.get(url, params=params)
        response.raise_for_status()
        hits = response.json().get("hits", [])
        if not hits:
            return None
        return hits[0]["objectID"]

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        thread_id = await self._find_latest_thread()
        if not thread_id:
            return []
        url = f"{self._base_url}/items/{thread_id}"
        response = await self._http.get(url)
        response.raise_for_status()
        data = response.json()
        jobs: list[RawJobListing] = []
        for child in data.get("children", []):
            if child.get("type") != "comment":
                continue
            text = child.get("text", "")
            if not text or "|" not in text:
                continue
            if _is_seeker_post(text):
                continue
            jobs.append(
                RawJobListing(
                    source="hn_hiring",
                    source_id=str(child["id"]),
                    raw_data={
                        "id": child["id"],
                        "author": child.get("author", ""),
                        "text": text,
                        "created_at": child.get("created_at", ""),
                        "created_at_i": child.get("created_at_i", 0),
                        "thread_id": thread_id,
                    },
                )
            )
        return jobs

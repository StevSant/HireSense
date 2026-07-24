"""CrunchBoard official RSS feed adapter."""

from __future__ import annotations

from typing import Any

import feedparser

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers.crunchboard_title import parse_crunchboard_title
from hiresense.kernel.value_objects import SourceType

__all__ = ["CrunchBoardAdapter", "parse_crunchboard_title"]


class CrunchBoardAdapter:
    """TechCrunch CrunchBoard jobs.rss — latest-window feed, not a snapshot."""

    def __init__(
        self,
        http_client: Any,
        *,
        rss_url: str = "https://www.crunchboard.com/jobs.rss",
        result_limit: int = 200,
    ) -> None:
        self._http = http_client
        self._rss_url = rss_url
        self._result_limit = max(1, result_limit)
        self.last_pages_fetched = 0
        self.last_parse_failures = 0
        self.last_rejected_malformed = 0

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "crunchboard"

    def source_type(self) -> SourceType:
        return SourceType.RSS

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
        self.last_pages_fetched = 0
        self.last_parse_failures = 0
        self.last_rejected_malformed = 0
        response = await self._http.get(self._rss_url)
        response.raise_for_status()
        self.last_pages_fetched = 1
        feed = feedparser.parse(response.text)
        jobs: list[RawJobListing] = []
        seen: set[str] = set()
        search = ((filters or {}).get("search") or "").strip().lower()
        for entry in feed.entries:
            link = entry.get("link") or entry.get("id") or ""
            guid = str(entry.get("id") or link)
            source_id = ""
            if "jobs/" in guid:
                source_id = guid.rstrip("/").rsplit("/", 1)[-1]
            elif link:
                source_id = link.rstrip("/").rsplit("/", 1)[-1]
            if not source_id:
                self.last_rejected_malformed += 1
                continue
            if source_id in seen:
                continue
            title = entry.get("title") or ""
            if (
                search
                and search not in title.lower()
                and search not in (entry.get("summary") or "").lower()
            ):
                continue
            seen.add(source_id)
            jobs.append(
                RawJobListing(
                    source="crunchboard",
                    source_id=source_id,
                    raw_data={
                        "title": title,
                        "link": link,
                        "guid": guid,
                        "published": entry.get("published", ""),
                        "summary": entry.get("summary", ""),
                        "tags": [t.term for t in entry.get("tags", []) if getattr(t, "term", None)],
                    },
                )
            )
            if len(jobs) >= self._result_limit:
                break
        return jobs

from __future__ import annotations

from typing import Any

import feedparser

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class WeWorkRemotelyAdapter:
    def __init__(self, http_client: Any, rss_url: str) -> None:
        self._http = http_client
        self._rss_url = rss_url

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "weworkremotely"

    def source_type(self) -> SourceType:
        return SourceType.RSS

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        response = await self._http.get(self._rss_url)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        jobs: list[RawJobListing] = []
        for entry in feed.entries:
            link = entry.get("link", "")
            slug = link.rstrip("/").rsplit("/", 1)[-1] if link else ""
            jobs.append(
                RawJobListing(
                    source="weworkremotely",
                    source_id=slug,
                    raw_data={
                        "title": entry.get("title", ""),
                        "link": link,
                        "published": entry.get("published", ""),
                        "summary": entry.get("summary", ""),
                        "category": entry.get("category", ""),
                        "region": entry.get("region", ""),
                        "type": entry.get("type", ""),
                        "skills": entry.get("skills", ""),
                    },
                )
            )
        return jobs

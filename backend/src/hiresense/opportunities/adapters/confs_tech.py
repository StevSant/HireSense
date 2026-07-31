from __future__ import annotations

import hashlib
import logging
from typing import Any
from urllib.parse import quote

from hiresense.opportunities.domain.models import RawOpportunity

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = (
    "https://raw.githubusercontent.com/tech-conferences/conference-data/main/conferences"
)


class ConfsTechAdapter:
    """Fetch conference JSON files from the confs.tech open data repo."""

    def __init__(
        self,
        http_client: Any,
        *,
        topics: list[str],
        years: list[int],
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._http = http_client
        self._topics = topics
        self._years = years
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def source_name(self) -> str:
        return "confs_tech"

    async def fetch(self, filters: dict[str, Any] | None = None) -> list[RawOpportunity]:
        topics = list((filters or {}).get("topics") or self._topics)
        years = list((filters or {}).get("years") or self._years)
        results: list[RawOpportunity] = []
        seen: set[str] = set()
        for year in years:
            for topic in topics:
                url = f"{self._base_url}/{year}/{quote(topic)}.json"
                try:
                    response = await self._http.get(url, timeout=self._timeout)
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    payload = response.json()
                except Exception:  # noqa: BLE001 — skip missing/bad topic files
                    logger.warning("confs.tech fetch failed for %s/%s", year, topic, exc_info=True)
                    continue
                if not isinstance(payload, list):
                    continue
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    name = (item.get("name") or "").strip()
                    item_url = (item.get("url") or "").strip()
                    if not name or not item_url:
                        continue
                    source_id = self._stable_id(year=year, topic=topic, item=item)
                    if source_id in seen:
                        continue
                    seen.add(source_id)
                    results.append(
                        RawOpportunity(
                            source="confs_tech",
                            source_id=source_id,
                            raw_data={**item, "topic": topic, "year": year},
                        )
                    )
        return results

    @staticmethod
    def _stable_id(*, year: int, topic: str, item: dict[str, Any]) -> str:
        seed = f"{year}|{topic}|{item.get('name', '')}|{item.get('url', '')}|{item.get('startDate', '')}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]

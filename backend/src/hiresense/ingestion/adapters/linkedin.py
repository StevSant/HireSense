from __future__ import annotations

import asyncio
import re
from typing import Any

from bs4 import BeautifulSoup

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
MAX_PAGES = 4
PAGE_SIZE = 25
REQUEST_DELAY = 2.0


class LinkedInAdapter:
    def __init__(self, http_client: Any, base_url: str) -> None:
        self._http = http_client
        self._base_url = base_url

    def source_name(self) -> str:
        return "linkedin"

    def source_type(self) -> SourceType:
        return SourceType.SCRAPER

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        keywords = filters.get("keywords", "software engineer") if filters else "software engineer"
        location = filters.get("location", "") if filters else ""
        headers = {"User-Agent": USER_AGENT}
        jobs: list[RawJobListing] = []
        for page in range(MAX_PAGES):
            start = page * PAGE_SIZE
            url = f"{self._base_url}/seeMoreJobPostings/search"
            params: dict[str, str] = {
                "keywords": keywords,
                "start": str(start),
                "f_WT": "2",
            }
            if location:
                params["location"] = location
            try:
                response = await self._http.get(url, params=params, headers=headers)
                if response.status_code == 429:
                    break
                response.raise_for_status()
            except Exception:
                import logging
                logging.getLogger(__name__).exception("LinkedIn request failed on page %d", page)
                break
            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.find_all("div", class_="base-card")
            if not cards:
                break
            for card in cards:
                parsed = self._parse_card(card)
                if parsed:
                    jobs.append(
                        RawJobListing(
                            source="linkedin",
                            source_id=parsed["job_id"],
                            raw_data=parsed,
                        )
                    )
            if page < MAX_PAGES - 1:
                await asyncio.sleep(REQUEST_DELAY)
        return jobs

    def _parse_card(self, card: Any) -> dict[str, str] | None:
        link_tag = card.find("a", class_="base-card__full-link")
        if not link_tag:
            return None
        href = link_tag.get("href", "")
        job_id = self._extract_job_id(href)
        if not job_id:
            return None
        title_tag = card.find("h3", class_="base-search-card__title")
        company_tag = card.find("h4", class_="base-search-card__subtitle")
        location_tag = card.find("span", class_="job-search-card__location")
        return {
            "job_id": job_id,
            "title": title_tag.get_text(strip=True) if title_tag else "",
            "company": company_tag.get_text(strip=True) if company_tag else "",
            "location": location_tag.get_text(strip=True) if location_tag else "",
            "url": href.split("?")[0],
        }

    @staticmethod
    def _extract_job_id(url: str) -> str:
        match = re.search(r"/view/(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"-(\d+)\?", url)
        return match.group(1) if match else ""

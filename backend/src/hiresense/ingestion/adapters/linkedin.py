from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
MAX_PAGES = 4
PAGE_SIZE = 25
REQUEST_DELAY = 2.0
DEFAULT_DETAIL_CONCURRENCY = 1
DEFAULT_DETAIL_DELAY = 1.0


class LinkedInAdapter:
    def __init__(
        self,
        http_client: Any,
        base_url: str,
        detail_concurrency: int = DEFAULT_DETAIL_CONCURRENCY,
        detail_delay: float = DEFAULT_DETAIL_DELAY,
    ) -> None:
        self._http = http_client
        self._base_url = base_url
        self._detail_concurrency = detail_concurrency
        self._detail_delay = detail_delay

    def supports_snapshot_closure(self) -> bool:
        return False

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
        cards: list[dict[str, str]] = []
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
                logger.exception("LinkedIn request failed on page %d", page)
                break
            soup = BeautifulSoup(response.text, "html.parser")
            page_cards = soup.find_all("div", class_="base-card")
            if not page_cards:
                break
            for card in page_cards:
                parsed = self._parse_card(card)
                if parsed:
                    cards.append(parsed)
            if page < MAX_PAGES - 1:
                await asyncio.sleep(REQUEST_DELAY)

        await self._enrich_with_details(cards, headers)

        return [
            RawJobListing(
                source="linkedin",
                source_id=c["job_id"],
                raw_data=c,
            )
            for c in cards
        ]

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
        time_tag = card.find("time")
        posted_date = ""
        if time_tag and time_tag.get("datetime"):
            posted_date = time_tag.get("datetime", "").strip()
        return {
            "job_id": job_id,
            "title": title_tag.get_text(strip=True) if title_tag else "",
            "company": company_tag.get_text(strip=True) if company_tag else "",
            "location": location_tag.get_text(strip=True) if location_tag else "",
            "url": href.split("?")[0],
            "posted_date": posted_date,
            "description": "",
        }

    async def _enrich_with_details(
        self,
        cards: list[dict[str, str]],
        headers: dict[str, str],
    ) -> None:
        semaphore = asyncio.Semaphore(self._detail_concurrency)

        async def fetch_one(card: dict[str, str]) -> None:
            async with semaphore:
                await asyncio.sleep(self._detail_delay)
                detail = await self._fetch_detail(card["job_id"], headers)
                if detail:
                    card.update(detail)

        await asyncio.gather(*(fetch_one(c) for c in cards))

        enriched = sum(1 for c in cards if c.get("description"))
        logger.info("LinkedIn detail enrichment: %d/%d jobs enriched", enriched, len(cards))

    async def _fetch_detail(
        self,
        job_id: str,
        headers: dict[str, str],
    ) -> dict[str, str] | None:
        url = f"{self._base_url}/jobPosting/{job_id}"
        try:
            response = await self._http.get(url, headers=headers)
            if response.status_code == 429:
                logger.warning("LinkedIn detail fetch rate-limited for %s", job_id)
                return None
            response.raise_for_status()
        except Exception:
            logger.exception("LinkedIn detail fetch failed for %s", job_id)
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        desc_tag = soup.find("div", class_="show-more-less-html__markup")
        description = strip_html(str(desc_tag)) if desc_tag else ""

        criteria: dict[str, str] = {}
        for item in soup.find_all("li", class_="description__job-criteria-item"):
            header = item.find("h3", class_="description__job-criteria-subheader")
            value = item.find("span", class_="description__job-criteria-text")
            if header and value:
                criteria[header.get_text(strip=True).lower()] = value.get_text(strip=True)

        return {
            "description": description,
            "seniority": criteria.get("seniority level", ""),
            "employment_type": criteria.get("employment type", ""),
            "job_function": criteria.get("job function", ""),
            "industries": criteria.get("industries", ""),
        }

    @staticmethod
    def _extract_job_id(url: str) -> str:
        match = re.search(r"/view/(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"-(\d+)\?", url)
        return match.group(1) if match else ""

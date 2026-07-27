from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.portal_config import PortalEntry
from hiresense.ingestion.ports import PageRendererPort
from hiresense.kernel.value_objects import SourceType


class GenericScraperAdapter:
    """Config-driven fallback scraper for proprietary careers pages."""

    def __init__(self, http_client: Any, renderer: PageRendererPort | None, timeout: float) -> None:
        self._http = http_client
        self._renderer = renderer
        self._timeout = timeout

    def supports_snapshot_closure(self) -> bool:
        return True

    def source_name(self) -> str:
        return "scraper"

    def source_type(self) -> SourceType:
        return SourceType.SCRAPER

    async def fetch_portal(self, portal: PortalEntry) -> list[RawJobListing]:
        if not portal.careers_url:
            raise ValueError(f"Scraper portal {portal.name} requires careers_url")
        html = await self._load_html(portal.careers_url, portal.render)
        soup = BeautifulSoup(html, "html.parser")

        link_selector = portal.selectors.get("job_links") or "a[href*='job'], a[href*='careers']"
        title_selector = portal.selectors.get("title") or "h1"
        location_selector = portal.selectors.get("location") or "[class*='location']"
        description_selector = portal.selectors.get("description") or "main, article, .job-description"
        href_regex = portal.selectors.get("href_regex")
        href_pattern = re.compile(href_regex) if href_regex else None
        skip_detail = (portal.selectors.get("skip_detail") or "").lower() in {"1", "true", "yes"}
        max_jobs_raw = portal.selectors.get("max_jobs")
        max_jobs = int(max_jobs_raw) if max_jobs_raw else None

        jobs: list[RawJobListing] = []
        seen: set[str] = set()
        for anchor in soup.select(link_selector):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            if href_pattern is not None and href_pattern.search(href) is None:
                continue
            url = urljoin(portal.careers_url, href)
            if url in seen:
                continue
            seen.add(url)
            anchor_title = anchor.get_text(" ", strip=True)
            if skip_detail:
                title = anchor_title
                location = ""
                description_html = ""
            else:
                detail_html = await self._load_html(url, portal.render)
                detail = BeautifulSoup(detail_html, "html.parser")
                title_el = detail.select_one(title_selector)
                title = title_el.get_text(" ", strip=True) if title_el else anchor_title
                location_el = detail.select_one(location_selector)
                description_el = detail.select_one(description_selector)
                location = location_el.get_text(" ", strip=True) if location_el else ""
                description_html = str(description_el) if description_el else detail_html
            if not title:
                continue
            jobs.append(
                RawJobListing(
                    source="scraper",
                    source_id=url.rstrip("/").rsplit("/", 1)[-1],
                    raw_data={
                        "title": title,
                        "company": portal.name,
                        "url": url,
                        "location": location,
                        "description_html": description_html,
                    },
                )
            )
            if max_jobs is not None and len(jobs) >= max_jobs:
                break
        return jobs

    async def _load_html(self, url: str, render_mode: str) -> str:
        if render_mode == "browser":
            if self._renderer is None:
                raise ValueError("Browser rendering requested but no Playwright renderer is configured")
            return await self._renderer.render(url)
        response = await self._http.get(url, timeout=self._timeout)
        response.raise_for_status()
        return response.text

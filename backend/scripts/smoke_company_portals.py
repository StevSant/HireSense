"""Live smoke checks for hardened company portal adapters."""

from __future__ import annotations

import asyncio
import re

import httpx

from hiresense.ingestion.adapters.generic_scraper_adapter import GenericScraperAdapter
from hiresense.ingestion.adapters.globant_adapter import GlobantAdapter
from hiresense.ingestion.adapters.thoughtworks_adapter import ThoughtworksAdapter
from hiresense.ingestion.domain.portal_config import PortalEntry


async def main() -> int:
    async with httpx.AsyncClient(
        timeout=45.0,
        follow_redirects=True,
        headers={"User-Agent": "HireSenseSmoke/1.0"},
    ) as client:
        tw = ThoughtworksAdapter(http_client=client, timeout=45.0)
        tw_jobs = await tw.fetch_portal(
            PortalEntry(
                name="Thoughtworks",
                platform="thoughtworks",
                board_id="thoughtworks",
                careers_url="https://www.thoughtworks.com/careers",
            )
        )
        print("thoughtworks", len(tw_jobs))
        assert len(tw_jobs) > 10

        gl = GlobantAdapter(http_client=client, timeout=45.0, max_pages=2)
        gl_jobs = await gl.fetch_portal(
            PortalEntry(
                name="Globant",
                platform="globant",
                board_id="globant",
                careers_url="https://career.globant.com/",
            )
        )
        print("globant", len(gl_jobs))
        assert len(gl_jobs) >= 10

        scraper = GenericScraperAdapter(http_client=client, renderer=None, timeout=45.0)
        cg_jobs = await scraper.fetch_portal(
            PortalEntry(
                name="Cognizant",
                platform="scraper",
                board_id="cognizant",
                careers_url="https://careers.cognizant.com/global-en/jobs",
                render="http",
                selectors={
                    "job_links": "a[href*='/jobs/']",
                    "href_regex": r"/jobs/\d+",
                    "skip_detail": "true",
                    "max_jobs": "20",
                },
            )
        )
        print("cognizant", len(cg_jobs))
        assert len(cg_jobs) >= 5
        assert all(re.search(r"/jobs/\d+", j.raw_data["url"]) for j in cg_jobs)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

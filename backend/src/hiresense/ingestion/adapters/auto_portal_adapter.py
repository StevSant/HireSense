from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from hiresense.ingestion.domain.portal_config import PortalEntry


class AutoPortalAdapter:
    """API-first router for company careers pages, else generic scraper."""

    def __init__(self, adapters: dict[str, Any], scraper_adapter: Any) -> None:
        self._adapters = adapters
        self._scraper = scraper_adapter

    def supports_snapshot_closure(self) -> bool:
        return True

    def detect_platform(self, portal: PortalEntry) -> str:
        return self._detect_platform(portal)

    async def fetch_portal(self, portal: PortalEntry):
        detected = self._detect_platform(portal)
        if detected == "scraper":
            return await self._scraper.fetch_portal(portal)
        adapter = self._adapters[detected]
        patched = self._patch_portal(portal, detected)
        if hasattr(adapter, "fetch_portal"):
            return await adapter.fetch_portal(patched)
        return await adapter.fetch_jobs(patched.board_id, patched.name)

    def _detect_platform(self, portal: PortalEntry) -> str:
        text = f"{portal.board_id} {portal.careers_url or ''}".lower()
        parsed = urlparse(portal.careers_url or portal.board_id or "")
        host = parsed.netloc.lower()
        if "greenhouse" in text:
            return "greenhouse"
        if "lever.co" in text:
            return "lever"
        if "ashbyhq" in text:
            return "ashby"
        if "smartrecruiters" in text:
            return "smartrecruiters"
        if "recruitee" in text:
            return "recruitee"
        if "workable" in text:
            return "workable"
        if "myworkdayjobs" in host or "/wday/cxs/" in text:
            return "workday"
        if "thoughtworks.com" in host or "thoughtworks" in text:
            return "thoughtworks"
        if "career.globant.com" in host or "globant" in text:
            return "globant"
        return "scraper"

    def _patch_portal(self, portal: PortalEntry, platform: str) -> PortalEntry:
        if platform == "greenhouse":
            board_id = self._extract_last_segment(portal, "greenhouse")
        elif platform == "lever":
            board_id = self._extract_last_segment(portal, "lever")
        elif platform == "ashby":
            board_id = self._extract_last_segment(portal, "ashby")
        elif platform == "smartrecruiters":
            board_id = self._extract_after(portal, "/company/")
        elif platform == "recruitee":
            host = urlparse(portal.careers_url or portal.board_id).netloc
            board_id = host.split(".")[0]
        elif platform == "workable":
            board_id = self._extract_last_segment(portal, "workable")
        else:
            board_id = portal.board_id
        return portal.model_copy(
            update={"platform": platform, "board_id": board_id or portal.board_id}
        )

    @staticmethod
    def _extract_last_segment(portal: PortalEntry, _platform: str) -> str:
        text = (portal.careers_url or portal.board_id or "").rstrip("/")
        return text.rsplit("/", 1)[-1]

    @staticmethod
    def _extract_after(portal: PortalEntry, marker: str) -> str:
        text = portal.careers_url or portal.board_id or ""
        if marker in text:
            return text.split(marker, 1)[1].split("/", 1)[0]
        return portal.board_id

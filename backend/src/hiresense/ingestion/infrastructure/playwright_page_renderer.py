from __future__ import annotations

from playwright.async_api import async_playwright


class PlaywrightPageRenderer:
    def __init__(self, timeout_ms: int = 30000) -> None:
        self._timeout_ms = timeout_ms

    async def render(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=self._timeout_ms)
                return await page.content()
            finally:
                await browser.close()

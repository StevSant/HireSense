from __future__ import annotations

from typing import Any


class PlaywrightDriver:
    """Drives the candidate's own Chrome over the DevTools Protocol.

    Connecting to a real, already-signed-in browser rather than launching a
    fresh headless one is the whole point: board sessions stay authenticated,
    the fingerprint is a genuine human's, and file uploads work.

    Playwright is imported lazily so the backend image and CI never need it.
    Install it with `uv sync --extra agent && uv run playwright install chromium`.
    """

    def __init__(self, cdp_url: str) -> None:
        self._cdp_url = cdp_url
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None

    async def start(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "Playwright is not installed. Run: uv sync --extra agent "
                "&& uv run playwright install chromium"
            ) from exc

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(self._cdp_url)
        context = (
            self._browser.contexts[0]
            if self._browser.contexts
            else await self._browser.new_context()
        )
        self._page = await context.new_page()

    async def goto(self, url: str) -> None:
        await self._page.goto(url, wait_until="domcontentloaded")

    async def html(self) -> str:
        return await self._page.content()

    async def url(self) -> str:
        return self._page.url

    async def title(self) -> str:
        return await self._page.title()

    async def fill(self, selector: str, value: str) -> None:
        await self._page.fill(selector, value)

    async def click(self, selector: str) -> None:
        await self._page.click(selector)

    async def upload(self, selector: str, path: str) -> None:
        await self._page.set_input_files(selector, path)

    async def text(self) -> str:
        return await self._page.inner_text("body")

    async def close(self) -> None:
        if self._page is not None:
            await self._page.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

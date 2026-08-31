from __future__ import annotations

import logging

from typing import Any

# Frame URLs that mean a human is being challenged. Mirrors the DOM
# serializer's rules, applied to frames the serializer cannot see.
_CHALLENGE_FRAME_PATHS = ("/bframe", "/challenge")
_INTERACTIVE_FRAME_SIZES = ("size=normal", "size=compact", "frame=checkbox")
_CAPTCHA_FRAME_HOSTS = (
    "recaptcha",
    "hcaptcha",
    "turnstile",
    "funcaptcha",
    "arkoselabs",
)

# Playwright locators pierce OPEN shadow roots, which a raw HTML dump does not.
_WIDGET_SELECTOR = ".g-recaptcha, .h-captcha, .cf-turnstile"


logger = logging.getLogger(__name__)


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

    async def challenge_present(self) -> bool:
        """Look where the serialized HTML cannot: frames and shadow roots.

        Closes the gap the DOM serializer documents. `page.frames` enumerates
        cross-origin children, and a Playwright locator pierces open shadow
        roots, so a widget rendered by `grecaptcha.render()` into a custom
        element is still found.

        Best-effort: a driver error here must never abort a run, and returning
        False just leaves detection where it was.
        """
        try:
            for frame in self._page.frames:
                src = (frame.url or "").casefold()
                if not any(host in src for host in _CAPTCHA_FRAME_HOSTS):
                    continue
                if any(path in src for path in _CHALLENGE_FRAME_PATHS):
                    return True
                if any(size in src for size in _INTERACTIVE_FRAME_SIZES):
                    return True

            locator = self._page.locator(_WIDGET_SELECTOR)
            for index in range(min(await locator.count(), 5)):
                if await locator.nth(index).is_visible():
                    return True
        except Exception:  # noqa: BLE001 - detection is advisory, never fatal
            logger.exception("runner: challenge detection failed")
        return False

    async def close(self) -> None:
        if self._page is not None:
            await self._page.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

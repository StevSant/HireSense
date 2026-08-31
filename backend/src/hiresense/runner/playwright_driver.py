from __future__ import annotations

import logging
from typing import Any

from hiresense.runner.challenge_probe_error import ChallengeProbeError

# The detection rules live in one place. Importing them (rather than copying)
# is what stops the two detectors drifting apart -- they answer the same
# question about the same page, just from opposite sides of the HTML dump.
from hiresense.runner.dom_serializer import (
    CAPTCHA_FRAME_HOSTS,
    CAPTCHA_WIDGET_SELECTOR,
    CHALLENGE_FRAME_PATHS,
    INTERACTIVE_FRAME_SIZES,
)


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

        Raises ChallengeProbeError when it cannot tell. The caller escalates on
        that: "unknown" must never be reported to the server as "no challenge".
        """
        try:
            main = self._page.main_frame
            for frame in self._page.frames:
                # The host rules describe EMBEDDED frames. Applying them to the
                # page's own URL would flag a form whose query string merely
                # mentions a captcha path.
                if frame is main:
                    continue
                src = (frame.url or "").casefold()
                if not any(host in src for host in CAPTCHA_FRAME_HOSTS):
                    continue
                if any(path in src for path in CHALLENGE_FRAME_PATHS):
                    return True
                if any(size in src for size in INTERACTIVE_FRAME_SIZES):
                    return True

            # One round trip, no cap: `visible=true` filters inside the browser,
            # so there is no index ceiling to silently miss a widget behind and
            # no staleness window between counting and checking.
            return bool(
                await self._page.locator(f"{CAPTCHA_WIDGET_SELECTOR} >> visible=true").count()
            )
        except Exception as exc:  # noqa: BLE001 - re-raised as a typed probe failure
            raise ChallengeProbeError("could not determine whether a challenge is present") from exc

    async def close(self) -> None:
        if self._page is not None:
            await self._page.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

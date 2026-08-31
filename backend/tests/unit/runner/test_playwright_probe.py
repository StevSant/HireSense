"""The real PlaywrightDriver challenge probe, against a headless browser.

Opt-in, like the `pgvector` suite: these drive an actual Chromium, so the
default `uv run python -m pytest` stays fast and browser-free.

    uv sync --extra agent && uv run playwright install chromium
    uv run python -m pytest -m playwright

Every page here is synthetic (`page.set_content`). Nothing navigates to a real
job board -- the hardening spec forbids tests touching real employer pages.

These exist because the probe's own rules (frame hosts/paths/sizes, the widget
selector, visibility) previously had no coverage at all: the loop-level tests
used a fake driver returning a canned bool, so mutating the probe broke nothing.
"""

import pytest

from hiresense.runner.challenge_probe_error import ChallengeProbeError
from hiresense.runner.playwright_driver import PlaywrightDriver

pytestmark = pytest.mark.playwright


class _Driver(PlaywrightDriver):
    """PlaywrightDriver with a Page injected, bypassing CDP connect."""

    def __init__(self, page):
        self._page = page


@pytest.fixture()
async def page():
    playwright = pytest.importorskip("playwright.async_api")
    async with playwright.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Serve the captcha frames locally. The probe reads `frame.url`, so the
        # URL still has to look real, but nothing may actually leave the machine:
        # a test that reaches a third-party endpoint is flaky by construction
        # (one of these genuinely failed to load and reported
        # `chrome-error://chromewebdata/` instead of its URL).
        async def _stub(route):
            await route.fulfill(status=200, content_type="text/html", body="<html></html>")

        for pattern in ("**/recaptcha/**", "**/hcaptcha**", "**/arkoselabs**", "**/turnstile**"):
            await page.route(pattern, _stub)

        yield page
        await browser.close()


async def _probe(page, html: str) -> bool:
    await page.set_content(html)
    return await _Driver(page).challenge_present()


# --- must NOT block ------------------------------------------------------


async def test_clean_form_reports_no_challenge(page):
    html = '<form><input id="email" required /><button type="submit">Apply</button></form>'
    assert await _probe(page, html) is False


async def test_invisible_widget_is_not_a_challenge(page):
    """The exact shape a reCAPTCHA-protected posting carries. The probe must
    mirror the serializer here -- an earlier version dropped this exclusion and
    would have re-escalated every such posting."""
    html = (
        '<div class="g-recaptcha" data-size="invisible" style="width:256px;height:60px">badge</div>'
    )
    assert await _probe(page, html) is False


async def test_hidden_widget_is_not_a_challenge(page):
    html = '<div class="g-recaptcha" data-sitekey="k" style="display:none">x</div>'
    assert await _probe(page, html) is False


async def test_token_textarea_is_not_a_challenge(page):
    html = '<textarea class="g-recaptcha-response"></textarea>'
    assert await _probe(page, html) is False


# --- must block ----------------------------------------------------------


async def test_visible_widget_blocks(page):
    html = '<div class="g-recaptcha" data-sitekey="k" style="width:300px;height:78px">x</div>'
    assert await _probe(page, html) is True


async def test_widget_in_an_open_shadow_root_blocks(page):
    """The gap this probe exists to close: invisible to page.content()."""
    await page.set_content("<div id=host></div>")
    await page.evaluate(
        """() => {
            const root = document.getElementById("host").attachShadow({mode: "open"});
            const widget = document.createElement("div");
            widget.className = "g-recaptcha";
            widget.setAttribute("data-sitekey", "k");
            widget.style.width = "300px";
            widget.style.height = "78px";
            widget.textContent = "challenge";
            root.appendChild(widget);
        }"""
    )
    assert await _Driver(page).challenge_present() is True


async def test_widget_beyond_the_first_five_still_blocks(page):
    """There is no index cap: a visible widget after several inert stubs must
    still be found. A capped scan silently missed exactly this shape."""
    stubs = '<div class="g-recaptcha" style="display:none"></div>' * 6
    html = (
        stubs + '<div class="g-recaptcha" data-sitekey="k" style="width:300px;height:78px">x</div>'
    )
    assert await _probe(page, html) is True


async def test_challenge_frame_blocks(page):
    html = '<iframe src="https://www.google.com/recaptcha/api2/bframe?k=x"></iframe>'
    assert await _probe(page, html) is True


async def test_sized_anchor_frame_blocks(page):
    html = '<iframe src="https://www.google.com/recaptcha/api2/anchor?k=x&size=normal"></iframe>'
    assert await _probe(page, html) is True


async def test_enterprise_badge_anchor_frame_does_not_block(page):
    html = '<iframe src="https://www.recaptcha.net/recaptcha/enterprise/anchor?ar=1&k=x"></iframe>'
    assert await _probe(page, html) is False


# --- boundaries ----------------------------------------------------------


async def test_main_frame_url_is_not_matched(page):
    """Host rules describe embedded frames. A form whose own URL merely mentions
    a captcha path must not escalate."""
    await page.goto("data:text/html,<p>/recaptcha/api2/bframe</p>")
    assert await _Driver(page).challenge_present() is False


async def test_a_dead_page_raises_rather_than_reporting_no_challenge(page):
    driver = _Driver(page)
    await page.context.close()
    with pytest.raises(ChallengeProbeError):
        await driver.challenge_present()

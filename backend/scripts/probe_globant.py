"""Extend Globant probe: click CTA and capture XHR."""

from __future__ import annotations

import asyncio
import json

from playwright.async_api import async_playwright


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        bodies: list[tuple[str, str]] = []

        async def on_response(resp) -> None:
            url = resp.url
            if any(
                k in url.lower() for k in ["job", "search", "opening", "vacanc", "graphql", "/api"]
            ):
                try:
                    text = await resp.text()
                except Exception:  # noqa: BLE001
                    text = ""
                bodies.append((f"{resp.status} {resp.request.method} {url}", text[:500]))

        page.on("response", on_response)
        await page.goto("https://career.globant.com/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)
        # Try clicking the green CTA / search affordance
        for sel in [
            "button",
            "[role=button]",
            "a",
        ]:
            els = await page.query_selector_all(sel)
            for el in els:
                text = (await el.inner_text()).strip().lower()
                if "job" in text or "search" in text or "show me" in text or "innovate" in text:
                    print("click candidate", text[:80])
        # Fill first visible textbox and press Enter
        box = await page.query_selector("input:not([type=hidden])")
        if box:
            await box.click()
            await box.fill("python developer")
            await box.press("Enter")
            await page.wait_for_timeout(5000)
        print("final url", page.url)
        print("captured", len(bodies))
        for header, body in bodies[:30]:
            print(header)
            if body and ("{" in body or "[" in body):
                print(body[:300])
        hrefs = await page.eval_on_selector_all(
            "a",
            "els => els.map(e => ({h:e.href,t:(e.innerText||'').trim().slice(0,60)})).filter(x => /job/i.test(x.h+x.t)).slice(0,40)",
        )
        print("anchors", json.dumps(hrefs, indent=2)[:2000])
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

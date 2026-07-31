"""Render JS careers pages with Playwright and dump useful link/API clues."""

from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

TARGETS = [
    ("globant", "https://career.globant.com/"),
    ("thoughtworks", "https://www.thoughtworks.com/careers/jobs"),
    ("cognizant", "https://careers.cognizant.com/global-en/jobs"),
]


async def probe(label: str, url: str) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        api_hits: list[str] = []

        def on_response(resp) -> None:
            u = resp.url
            if any(
                k in u.lower() for k in ["job", "search", "posting", "career", "phapp", "widget"]
            ):
                if resp.status < 400:
                    api_hits.append(f"{resp.status} {u[:220]}")

        page.on("response", on_response)
        print(f"\n=== {label} render {url} ===")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2500)
        except Exception as exc:  # noqa: BLE001
            print("goto error:", exc)
        html = await page.content()
        print("html len", len(html))
        hrefs = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href: e.href, text: (e.innerText||'').trim().slice(0,80)}))",
        )
        jobish = [
            h
            for h in hrefs
            if any(k in (h.get("href") or "").lower() for k in ["/job", "jobs/", "careers/jobs"])
        ]
        print("jobish anchors", len(jobish))
        for h in jobish[:20]:
            print(" ", h["href"][:180], "|", h["text"])
        print("network hits", len(api_hits))
        for h in api_hits[:25]:
            print(" ", h)
        # Globant often has a search input — try submitting something
        if label == "globant":
            for sel in [
                "input[type=search]",
                "input[placeholder*='job']",
                "input[placeholder*='Show']",
                "input",
            ]:
                el = await page.query_selector(sel)
                if el:
                    print("found input", sel)
                    try:
                        await el.fill("python")
                        await el.press("Enter")
                        await page.wait_for_timeout(3000)
                        hrefs2 = await page.eval_on_selector_all(
                            "a[href*='job']",
                            "els => els.map(e => e.href).slice(0,20)",
                        )
                        print("after search job links", hrefs2)
                    except Exception as exc:  # noqa: BLE001
                        print("search attempt failed", exc)
                    break
        await browser.close()


async def main() -> None:
    for label, url in TARGETS:
        try:
            await probe(label, url)
        except Exception as exc:  # noqa: BLE001
            print(label, "FAILED", exc)


if __name__ == "__main__":
    asyncio.run(main())

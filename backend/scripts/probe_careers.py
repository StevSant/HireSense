"""One-off probe for company careers pages (selectors / hidden APIs)."""

from __future__ import annotations

import asyncio
import re

import httpx
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


async def peek(client: httpx.AsyncClient, url: str, label: str) -> None:
    r = await client.get(url)
    print(f"\n=== {label} {url} status={r.status_code} len={len(r.text)} ===")
    soup = BeautifulSoup(r.text, "html.parser")
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)[:80]
        if any(k in href.lower() for k in ["job", "career", "opening", "vacanc", "opportunity"]):
            links.append((href[:160], text))
    print("job-ish links:", len(links))
    for href, text in links[:15]:
        print(" ", href, "|", text)
    for pat in [
        r"https?://[^\"']+api[^\"']+",
        r"/wday/cxs/[^\"']+",
        r"greenhouse\.io[^\"']*",
        r"boards-api[^\"']*",
        r"phenompeople[^\"']*",
        r"smartrecruiters[^\"']*",
        r"jobPostings",
        r"/careers/jobs/\d+",
        r"/job/[^\"'\s]+",
    ]:
        m = re.findall(pat, r.text, flags=re.I)
        if m:
            uniq = list(dict.fromkeys(m))[:8]
            print("match", pat, "->", uniq)


async def main() -> None:
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30.0, headers={"User-Agent": UA}
    ) as client:
        await peek(client, "https://career.globant.com/", "globant-home")
        await peek(client, "https://www.thoughtworks.com/careers/jobs", "tw-jobs")
        await peek(client, "https://careers.cognizant.com/global-en/jobs", "cognizant-jobs")
        await peek(client, "https://job-boards.greenhouse.io/encora10", "encora-gh")
        # Cognizant often uses Phenom People JSON endpoints
        for url in [
            "https://careers.cognizant.com/global-en/widgets",
            "https://careers.cognizant.com/widgets",
            "https://cdn.phenompeople.com/CareerConnectResources/COGNGLOBAL/en_global/desktop/assets/js/app.js",
        ]:
            try:
                r = await client.get(url)
                print(f"\nextra {url} -> {r.status_code} ({len(r.text)} bytes)")
            except Exception as exc:  # noqa: BLE001
                print(f"\nextra {url} -> ERROR {exc}")


if __name__ == "__main__":
    asyncio.run(main())

"""Deeper Globant careers HTML analysis."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import httpx

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


async def main() -> None:
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True, headers=UA) as client:
        r = await client.get("https://career.globant.com/")
        out = Path("scripts/_globant_home.html")
        out.write_text(r.text, encoding="utf-8")
        print("saved", out, "bytes", len(r.text))
        # interesting tokens
        for pat in [
            r"myworkdayjobs",
            r"greenhouse",
            r"lever\.co",
            r"ashby",
            r"smartrecruiters",
            r"phenom",
            r"eightfold",
            r"successfactors",
            r"taleo",
            r"workday",
            r"graphql",
            r"algolia",
            r"__NEXT_DATA__",
            r"buildId",
            r"job-opening",
            r"/job/",
            r"api/",
        ]:
            hits = re.findall(pat, r.text, flags=re.I)
            if hits:
                print(pat, "count", len(hits), "sample", hits[:3])

        # script srcs
        scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', r.text, flags=re.I)
        print("scripts", len(scripts))
        for s in scripts[:30]:
            print(" ", s)

        # try common search query pages
        for url in [
            "https://career.globant.com/?page=1",
            "https://career.globant.com/search-jobs",
            "https://career.globant.com/job-search",
            "https://www.globant.com/careers",
            "https://www.globant.com/careers/open-positions",
        ]:
            rr = await client.get(url)
            jobish = re.findall(r'href=["\']([^"\']*job[^"\']*)["\']', rr.text, flags=re.I)
            print(url, rr.status_code, "bytes", len(rr.text), "jobish", len(jobish), jobish[:5])


if __name__ == "__main__":
    asyncio.run(main())

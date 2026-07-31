"""Find Globant SuccessFactors / job API endpoints in JS bundles."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import httpx

UA = {"User-Agent": "Mozilla/5.0"}


async def main() -> None:
    html = Path("scripts/_globant_home.html").read_text(encoding="utf-8")
    scripts = re.findall(r'src=["\'](/_next/static/chunks/[^"\']+)["\']', html)
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True, headers=UA) as client:
        interesting: list[str] = []
        for path in scripts:
            url = "https://career.globant.com" + path
            r = await client.get(url)
            text = r.text
            for pat in [
                r"https?://[^\"'\s]{10,200}",
                r"/services/[^\"'\s]{5,120}",
                r"jobRequisition[^\"'\s]{0,80}",
                r"searchJobs[^\"'\s]{0,80}",
                r"successfactors[^\"'\s]{0,120}",
                r"companyId[^\"'\s]{0,40}",
                r"rmk[^\"'\s]{0,80}",
            ]:
                for m in re.finditer(pat, text, flags=re.I):
                    s = m.group(0)
                    if any(
                        k in s.lower()
                        for k in [
                            "job",
                            "career",
                            "success",
                            "recruit",
                            "api",
                            "search",
                            "sap",
                            "odata",
                            "rmk",
                        ]
                    ):
                        interesting.append(s[:240])
        uniq = sorted(set(interesting))
        print("interesting", len(uniq))
        for u in uniq[:80]:
            print(u)

        # Try SuccessFactors RMK search endpoints with company hash from CDN
        company = "0a612432"
        guesses = [
            f"https://career.globant.com/services/recruiting/v1/jobRequisitions?company={company}",
            "https://career.globant.com/services/recruiting/v1/search",
            "https://career.globant.com/widgets",
            "https://career.globant.com/search/",
            "https://career.globant.com/jobboard/search",
            "https://api10.successfactors.com/career?company=globant",
            "https://performancemanager10.successfactors.com/career?company=globant",
        ]
        for g in guesses:
            try:
                rr = await client.get(g)
                print(
                    "GUESS",
                    rr.status_code,
                    g,
                    rr.headers.get("content-type", "")[:40],
                    len(rr.content),
                )
                if rr.status_code < 400 and (
                    "json" in (rr.headers.get("content-type") or "") or rr.text[:1] in "{["
                ):
                    print(" ", rr.text[:250].replace("\n", " "))
            except Exception as exc:  # noqa: BLE001
                print("GUESS fail", g, exc)


if __name__ == "__main__":
    asyncio.run(main())

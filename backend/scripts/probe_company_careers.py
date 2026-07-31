"""Live probe for Cognizant / Globant / Thoughtworks careers feeds."""

from __future__ import annotations

import asyncio
import re

import httpx

UA = {"User-Agent": "Mozilla/5.0 (compatible; HireSenseProbe/1.0)"}


async def probe_thoughtworks(client: httpx.AsyncClient) -> None:
    url = "https://www.thoughtworks.com/rest/careers/jobs"
    r = await client.get(url)
    print("THOUGHTWORKS", r.status_code)
    data = r.json()
    jobs = data.get("jobs") if isinstance(data, dict) else data
    print("  jobs", len(jobs) if isinstance(jobs, list) else type(jobs))
    if isinstance(jobs, list) and jobs:
        sample = jobs[0]
        print("  sample keys", sorted(sample.keys())[:20])
        print("  sample id/name", sample.get("sourceSystemId"), sample.get("name"))


async def probe_cognizant(client: httpx.AsyncClient) -> None:
    url = "https://careers.cognizant.com/global-en"
    r = await client.get(url)
    print("COGNIZANT", r.status_code, "bytes", len(r.text))
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', r.text, flags=re.I)
    jobish = [h for h in hrefs if re.search(r"/jobs/\d+", h)]
    print("  total hrefs", len(hrefs), "jobish", len(jobish))
    for h in jobish[:10]:
        print("   ", h)
    # Also try search listing pages commonly used by Phenom
    for candidate in (
        "https://careers.cognizant.com/global-en/jobs",
        "https://careers.cognizant.com/global-en/search/?q=&locationsearch=",
    ):
        try:
            rr = await client.get(candidate)
            hrefs2 = re.findall(r'href=["\']([^"\']*jobs[^"\']*)["\']', rr.text, flags=re.I)
            jobish2 = [h for h in hrefs2 if re.search(r"/jobs/\d+", h)]
            print(f"  alt {candidate} status={rr.status_code} jobish={len(jobish2)}")
            for h in jobish2[:5]:
                print("   ", h)
        except Exception as exc:  # noqa: BLE001
            print("  alt fail", candidate, exc)


async def probe_globant(client: httpx.AsyncClient) -> None:
    url = "https://career.globant.com/"
    r = await client.get(url)
    print("GLOBANT home", r.status_code, "bytes", len(r.text))
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', r.text, flags=re.I)
    print("  hrefs", len(hrefs))
    for h in [x for x in hrefs if "job" in x.lower()][:15]:
        print("   ", h)
    # Common Next.js data / API guesses
    guesses = [
        "https://career.globant.com/api/jobs",
        "https://career.globant.com/api/search",
        "https://career.globant.com/jobs",
        "https://career.globant.com/en/jobs",
        "https://career.globant.com/search",
        "https://career.globant.com/_next/data",
    ]
    for g in guesses:
        try:
            rr = await client.get(g)
            ctype = rr.headers.get("content-type", "")
            print(f"  guess {g} -> {rr.status_code} {ctype[:40]} bytes={len(rr.content)}")
            if "json" in ctype or rr.text.strip().startswith(("{", "[")):
                print("   json snip", rr.text[:200].replace("\n", " "))
        except Exception as exc:  # noqa: BLE001
            print("  guess fail", g, exc)

    # Look for buildId / next data URLs in HTML
    build = re.search(r'"buildId"\s*:\s*"([^"]+)"', r.text)
    print("  buildId", build.group(1) if build else None)
    for m in re.findall(r"/_next/data/[^\"'\s]+", r.text)[:10]:
        print("  nextdata", m)
    for m in re.findall(
        r"https?://[^\"'\s]*(?:api|graphql|algolia|search)[^\"'\s]*", r.text, flags=re.I
    )[:15]:
        print("  api-ish", m)


async def main() -> int:
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True, headers=UA) as client:
        await probe_thoughtworks(client)
        await probe_cognizant(client)
        await probe_globant(client)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

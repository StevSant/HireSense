"""Probe Globant /sap/job-requisition API."""

from __future__ import annotations

import asyncio
import json

import httpx

UA = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
}


async def main() -> None:
    urls = [
        "https://career.globant.com/sap/job-requisition?&page=1",
        "https://career.globant.com/sap/job-requisition?page=1",
        "https://career.globant.com/sap/job-requisition?&page=1&keyword=python",
        "https://career.globant.com/sap/job-requisition?page=0",
        "https://career.globant.com/api/sap/job-requisition?page=1",
    ]
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True, headers=UA) as client:
        for url in urls:
            r = await client.get(url)
            ctype = r.headers.get("content-type", "")
            print("\nURL", url)
            print("status", r.status_code, "ctype", ctype, "bytes", len(r.content))
            snip = r.text[:500].replace("\n", " ")
            print("snip", snip)
            if "json" in ctype or r.text.strip().startswith(("{", "[")):
                try:
                    data = r.json()
                    print("type", type(data).__name__)
                    if isinstance(data, dict):
                        print("keys", list(data.keys())[:30])
                        jr = data.get("jobRequisition") or data.get("jobRequisitions")
                        if isinstance(jr, list):
                            print("jobs", len(jr))
                            if jr:
                                print("sample", json.dumps(jr[0], indent=2)[:800])
                    elif isinstance(data, list):
                        print("list len", len(data))
                        if data:
                            print("sample", json.dumps(data[0], indent=2)[:800])
                except Exception as exc:  # noqa: BLE001
                    print("json parse fail", exc)


if __name__ == "__main__":
    asyncio.run(main())

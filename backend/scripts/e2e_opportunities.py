"""E2E smoke: login → fetch opportunities → list with filters.

Requires a running API and credentials via env:
  HS_BASE_URL (default http://127.0.0.1:8000)
  AUTH_USERNAME / AUTH_PASSWORD
"""

from __future__ import annotations

import os
import sys

import httpx

BASE = os.environ.get("HS_BASE_URL", "http://127.0.0.1:8000")
USER = os.environ.get("AUTH_USERNAME", "admin")
PASSWORD = os.environ.get("AUTH_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("Set AUTH_PASSWORD (and optionally AUTH_USERNAME / HS_BASE_URL).", file=sys.stderr)
        return 2
    with httpx.Client(base_url=BASE, timeout=180.0, follow_redirects=True) as client:
        login = client.post("/auth/login", json={"username": USER, "password": PASSWORD})
        print("login", login.status_code)
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        fetch = client.post("/opportunities/fetch", headers=headers)
        print("fetch", fetch.status_code, fetch.text[:500])
        fetch.raise_for_status()
        summary = fetch.json()
        print("sources", summary.get("sources"))
        print(
            "counts",
            {k: summary.get(k) for k in ("inserted", "updated", "reopened", "unchanged", "errors")},
        )

        listed = client.get(
            "/opportunities",
            headers=headers,
            params={"page": 1, "page_size": 10, "sort": "relevance_desc"},
        )
        print("list", listed.status_code)
        listed.raise_for_status()
        body = listed.json()
        print("total", body.get("total"), "page_items", len(body.get("items") or []))
        titles = [i.get("title") for i in (body.get("items") or [])[:8]]
        print("titles", titles)
        assert body.get("total", 0) > 0, "expected opportunities after fetch"

        funded = client.get(
            "/opportunities",
            headers=headers,
            params={"funded_only": True, "q": "khipu"},
        )
        funded.raise_for_status()
        funded_body = funded.json()
        print(
            "funded_q_khipu",
            funded_body.get("total"),
            [i["title"] for i in funded_body["items"][:5]],
        )

        # Frontend proxy path
        fe = httpx.get("http://127.0.0.1:4200/", timeout=30.0)
        print("frontend", fe.status_code, len(fe.text))
        assert fe.status_code == 200
    print("E2E OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print("E2E FAILED", exc, file=sys.stderr)
        raise

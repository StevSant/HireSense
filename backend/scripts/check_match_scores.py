import os

import httpx

BASE = "http://127.0.0.1:8000"
USER = os.environ.get("AUTH_USERNAME", "admin")
PASSWORD = os.environ.get("AUTH_PASSWORD")
if not PASSWORD:
    raise SystemExit("Set AUTH_PASSWORD before running this script.")

with httpx.Client(base_url=BASE, timeout=60.0) as c:
    token = c.post(
        "/auth/login",
        json={"username": USER, "password": PASSWORD},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    body = c.get(
        "/opportunities",
        headers=h,
        params={"page": 1, "page_size": 8, "sort": "match_desc", "matched_only": "true"},
    ).json()
    print("total", body.get("total"))
    for i in body.get("items") or []:
        score = i.get("relevance_score")
        print(f"{score!s:>6}  {i['title'][:40]:40}  {i['topics']}")

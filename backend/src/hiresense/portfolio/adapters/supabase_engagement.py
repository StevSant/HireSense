from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from hiresense.portfolio.domain import PortfolioVisit

# Session ids are interpolated into a PostgREST `in.(...)` filter; restrict
# them to UUID-safe characters so a value containing `,`, `)` or quotes can
# never rewrite the filter expression.
_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9-]+$")


def _parse_dt(value: str) -> datetime:
    """Parse ISO 8601 timestamp, handling the 'Z' suffix PostgREST may emit."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class SupabaseEngagementAdapter:
    """Reads aggregated portfolio visit analytics from Supabase via PostgREST.

    Requires the Supabase service_role key — visitor_session SELECT is
    restricted to authenticated/service-role only (anon key is blocked by RLS).
    """

    def __init__(self, http_client: Any, base_url: str, read_key: str) -> None:
        self._http = http_client
        self._base = base_url.rstrip("/")
        self._key = read_key

    async def _get(self, path: str, params: dict[str, str]) -> Any:
        response = await self._http.get(
            f"{self._base}{path}",
            headers={"apikey": self._key, "Authorization": f"Bearer {self._key}"},
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def fetch_visits(self, ref_prefix: str) -> list[PortfolioVisit]:
        sessions: list[dict[str, Any]] = await self._get(
            "/rest/v1/visitor_session",
            {
                "select": "id,referrer_source,started_at,last_seen_at,total_page_views,country,organization",
                "referrer_source": f"like.{ref_prefix}-*",
            },
        )

        if not sessions:
            return []

        # Tally cv_downloads per session_id from the cv_download table.
        session_ids = [
            sid for s in sessions if _SAFE_SESSION_ID.fullmatch(sid := str(s["id"]))
        ]
        downloads_raw: list[dict[str, Any]] = []
        if session_ids:
            downloads_raw = await self._get(
                "/rest/v1/cv_download",
                {
                    "select": "session_id",
                    "session_id": f"in.({','.join(session_ids)})",
                },
            )
        download_count_by_session: dict[str, int] = {}
        for row in downloads_raw:
            sid = str(row["session_id"])
            download_count_by_session[sid] = download_count_by_session.get(sid, 0) + 1

        # Group sessions by referrer_source.
        groups: dict[str, list[dict[str, Any]]] = {}
        for session in sessions:
            ref = session["referrer_source"]
            groups.setdefault(ref, []).append(session)

        visits: list[PortfolioVisit] = []
        for ref, group in groups.items():
            first_seen = min(_parse_dt(s["started_at"]) for s in group)
            last_seen_values = [_parse_dt(s["last_seen_at"]) for s in group]
            last_seen = max(last_seen_values)
            page_views = sum(s.get("total_page_views") or 0 for s in group)
            cv_downloads = sum(
                download_count_by_session.get(str(s["id"]), 0) for s in group
            )
            # country / organization from the session with the latest last_seen_at.
            latest_session = group[last_seen_values.index(last_seen)]
            visits.append(
                PortfolioVisit(
                    ref=ref,
                    first_seen=first_seen,
                    last_seen=last_seen,
                    page_views=page_views,
                    cv_downloads=cv_downloads,
                    country=latest_session.get("country"),
                    organization=latest_session.get("organization"),
                )
            )

        return visits

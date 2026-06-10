"""Tests for SupabaseEngagementAdapter.

Uses a fake HTTP client with canned payloads (same pattern as
test_supabase_adapter.py) to stay DB-free.
"""
from __future__ import annotations

import pytest


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._payload


class _FakeHttp:
    def __init__(self, payload_by_path: dict):
        self._payloads = payload_by_path
        self.calls: list[tuple[str, dict, dict]] = []

    async def get(self, url, headers=None, params=None):
        self.calls.append((url, dict(headers or {}), dict(params or {})))
        for path, payload in self._payloads.items():
            if path in url:
                return _FakeResponse(payload)
        raise AssertionError(f"unexpected url {url!r}")


# ---------------------------------------------------------------------------
# Test (a): grouping/aggregation + cv_download attribution
# Two sessions share "hiresense-app1", one session belongs to "hiresense-app2".
# cv_download rows: 2 for session 1, 1 for session 3.
# ---------------------------------------------------------------------------

_SESSIONS_MULTI = [
    {
        "id": "s1",
        "referrer_source": "hiresense-app1",
        "started_at": "2026-06-01T09:00:00Z",
        "last_seen_at": "2026-06-05T12:00:00Z",
        "total_page_views": 3,
        "country": "ES",
        "organization": "Acme",
    },
    {
        "id": "s2",
        "referrer_source": "hiresense-app1",
        "started_at": "2026-06-03T10:00:00Z",
        "last_seen_at": "2026-06-10T08:00:00Z",
        "total_page_views": 2,
        "country": "DE",
        "organization": "Beta GmbH",
    },
    {
        "id": "s3",
        "referrer_source": "hiresense-app2",
        "started_at": "2026-06-07T14:00:00Z",
        "last_seen_at": "2026-06-09T18:00:00Z",
        "total_page_views": 5,
        "country": "US",
        "organization": None,
    },
]

_CV_DOWNLOADS_MULTI = [
    {"session_id": "s1"},
    {"session_id": "s1"},  # 2 downloads for s1
    {"session_id": "s3"},  # 1 download for s3
]

_PAYLOADS_MULTI = {
    "/rest/v1/visitor_session": _SESSIONS_MULTI,
    "/rest/v1/cv_download": _CV_DOWNLOADS_MULTI,
}


@pytest.mark.asyncio
async def test_grouping_and_aggregation() -> None:
    from hiresense.portfolio.adapters import SupabaseEngagementAdapter

    http = _FakeHttp(_PAYLOADS_MULTI)
    adapter = SupabaseEngagementAdapter(
        http_client=http, base_url="https://xyz.supabase.co", read_key="svc-key"
    )
    visits = await adapter.fetch_visits("hiresense")

    by_ref = {v.ref: v for v in visits}
    assert set(by_ref) == {"hiresense-app1", "hiresense-app2"}

    v1 = by_ref["hiresense-app1"]
    # first_seen = min(s1.started_at, s2.started_at)
    assert v1.first_seen.isoformat() == "2026-06-01T09:00:00+00:00"
    # last_seen = max(s1.last_seen_at, s2.last_seen_at) → s2
    assert v1.last_seen.isoformat() == "2026-06-10T08:00:00+00:00"
    # page_views = 3 + 2
    assert v1.page_views == 5
    # cv_downloads = 2 (s1) + 0 (s2)
    assert v1.cv_downloads == 2
    # country/organization from the latest-last_seen session (s2)
    assert v1.country == "DE"
    assert v1.organization == "Beta GmbH"

    v2 = by_ref["hiresense-app2"]
    assert v2.page_views == 5
    assert v2.cv_downloads == 1
    assert v2.country == "US"
    assert v2.organization is None


# ---------------------------------------------------------------------------
# Test (b): zero sessions → no cv_download call, empty result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_sessions_no_second_query_and_empty_result() -> None:
    from hiresense.portfolio.adapters import SupabaseEngagementAdapter

    http = _FakeHttp({"/rest/v1/visitor_session": []})
    adapter = SupabaseEngagementAdapter(
        http_client=http, base_url="https://xyz.supabase.co", read_key="svc-key"
    )
    visits = await adapter.fetch_visits("hiresense")

    assert visits == []
    # Only one HTTP call should have been made (the session query).
    assert len(http.calls) == 1
    assert "/rest/v1/visitor_session" in http.calls[0][0]


# ---------------------------------------------------------------------------
# Test (c): auth headers carry the read key on both endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_headers_on_both_endpoints() -> None:
    from hiresense.portfolio.adapters import SupabaseEngagementAdapter

    captured: list[dict] = []

    class _TrackedHttp(_FakeHttp):
        async def get(self, url, headers=None, params=None):
            captured.append(dict(headers or {}))
            return await super().get(url, headers=headers, params=params)

    http = _TrackedHttp(_PAYLOADS_MULTI)
    adapter = SupabaseEngagementAdapter(
        http_client=http, base_url="https://xyz.supabase.co", read_key="my-service-key"
    )
    await adapter.fetch_visits("hiresense")

    # Both the session query and cv_download query should carry the key.
    assert len(captured) == 2
    for headers in captured:
        assert headers.get("apikey") == "my-service-key"
        assert headers.get("Authorization") == "Bearer my-service-key"

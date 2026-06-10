# Portfolio Phase 5 (Engagement Readback) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read back portfolio visits driven by Phase 3's tracked links (`?ref=hiresense-<application_id>`) and surface "Portfolio visited — N page views, last seen …" on the application detail page plus an engagement card on the analytics dashboard.

**Key facts (verified against the portfolio repo's RLS):**
- The portfolio records `?ref=` into `visitor_session.referrer_source`; sessions carry `started_at`, `last_seen_at`, `total_page_views`, `country`, `organization`.
- `visitor_session` SELECT requires an authenticated/service role — the anon key CANNOT read it. The adapter therefore uses a dedicated `PORTFOLIO_ANALYTICS_READ_KEY` (the Supabase **service_role** key, which bypasses RLS; the user pastes it from Supabase Dashboard → Settings → API). Feature is entirely absent when unset.
- `cv_download(session_id, ...)` is readable with the same key; counts ride along.
- PostgREST query shapes:
  - `GET {base}/rest/v1/visitor_session?select=id,referrer_source,started_at,last_seen_at,total_page_views,country,organization&referrer_source=like.{prefix}-*`
  - `GET {base}/rest/v1/cv_download?select=session_id&session_id=in.(<comma ids>)`
  - Headers: `apikey: <key>`, `Authorization: Bearer <key>`.

**Working directory:** `C:\Users\Bryan\worktrees\hiresense-portfolio` (branch `feat/portfolio-engagement`, stacked on `feat/network-linkedin`; PR base = that branch). **Quirks:** `uv run python -m pytest` only; no repo-wide `ruff format`; frontend lint via `npx ng lint`; commit trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

**Failure semantics:** read key unset → endpoint returns `{"configured": false, "visits": []}` and the frontend renders nothing. Adapter/network errors → log warning, return `{"configured": true, "visits": []}` ("no data", never a 5xx for a dashboard accessory).

---

### Task 1: Config + `PortfolioVisit` + engagement port

**Files:** modify `backend/src/hiresense/config.py`, `.env.example` (+ local `.env` gets the empty key); create `portfolio/domain/portfolio_visit.py`, `portfolio/ports/engagement_source.py`; modify both `__init__.py`s; tests appended to `tests/unit/test_config.py` + new `tests/unit/portfolio/test_visit_model.py`

- Config (portfolio block): `portfolio_analytics_read_key: str = ""` with comment "Supabase service_role key for reading visitor analytics (Dashboard → Settings → API). Empty disables engagement readback entirely." Config test pins it via monkeypatch and asserts default "".
- `PortfolioVisit` (pydantic): `ref: str`, `application_id: str | None = None`, `first_seen: datetime`, `last_seen: datetime`, `page_views: int = 0`, `cv_downloads: int = 0`, `country: str | None = None`, `organization: str | None = None`.
- `PortfolioEngagementPort(Protocol)`: `async fetch_visits(self, ref_prefix: str) -> list[PortfolioVisit]` (visits grouped per ref; `application_id` left None — the service derives it).
- Model test: construction defaults; that's it (pure data).
- `.env.example` line; local `.env` gets `PORTFOLIO_ANALYTICS_READ_KEY=` (empty — the user fills it later).
- **Commit:** `feat(portfolio): engagement visit model and port`.

---

### Task 2: `SupabaseEngagementAdapter`

**Files:** create `portfolio/adapters/supabase_engagement.py`; modify `adapters/__init__.py`; test `tests/unit/portfolio/test_supabase_engagement_adapter.py`

Implementation contract (mirror `supabase_portfolio.py` style — fake http client tests with canned payloads):

```python
class SupabaseEngagementAdapter:
    def __init__(self, http_client, base_url: str, read_key: str) -> None: ...
    async def fetch_visits(self, ref_prefix: str) -> list[PortfolioVisit]: ...
```

- Query 1: visitor_session filtered `referrer_source=like.{ref_prefix}-*` (params dict: `{"select": "id,referrer_source,started_at,last_seen_at,total_page_views,country,organization", "referrer_source": f"like.{ref_prefix}-*"}`), raise_for_status.
- Query 2 (only when sessions exist): cv_download with `{"select": "session_id", "session_id": f"in.({','.join(ids)})"}` → count per session_id.
- Group sessions by `referrer_source` → one `PortfolioVisit` per ref: `first_seen=min(started_at)`, `last_seen=max(last_seen_at)`, `page_views=sum(total_page_views or 0)`, `cv_downloads=sum(counts of that ref's sessions)`, `country`/`organization` from the session with the latest `last_seen_at` (may be None). Parse timestamps with `datetime.fromisoformat` (PostgREST emits ISO 8601; handle the `Z`→`+00:00` replacement if needed).
- Tests: (a) two sessions sharing one ref + one with another ref → grouped correctly, sums/min/max right, cv_download counts attributed; (b) zero sessions → no second query, empty list; (c) auth headers carry the read key.
- **Commit:** `feat(portfolio): supabase engagement adapter`.

---

### Task 3: Engagement service + endpoint + bootstrap

**Files:** create `portfolio/domain/engagement_service.py` (re-export); modify `portfolio/api/provider.py` (optional `engagement_service=None` param + getter), `portfolio/api/dependencies.py` (`get_engagement_service` None-degrading), `portfolio/api/routes.py` (new GET), `bootstrap/portfolio.py`; tests `tests/unit/portfolio/test_engagement_service.py` + extend `tests/unit/portfolio/test_routes.py` + `test_bootstrap.py`

- `PortfolioEngagementService(source: PortfolioEngagementPort, *, ref_prefix: str)`: `async visits() -> list[PortfolioVisit]` — calls `source.fetch_visits(ref_prefix)`, sets `application_id = ref.removeprefix(f"{ref_prefix}-")` when the ref has that prefix (else None), sorts by `last_seen` desc. Exceptions: catch, `logger.warning`, return [] (the "no data" rule).
- Route:

```python
class EngagementResponse(BaseModel):
    configured: bool
    visits: list[PortfolioVisit]


@router.get("/engagement", response_model=EngagementResponse)
async def engagement(
    service: Annotated[PortfolioEngagementService | None, Depends(get_engagement_service)],
) -> EngagementResponse:
    if service is None:
        return EngagementResponse(configured=False, visits=[])
    return EngagementResponse(configured=True, visits=await service.visits())
```

- Bootstrap: build engagement only when `s.portfolio_analytics_read_key` AND `s.portfolio_supabase_url` are both non-empty:

```python
    engagement_service = None
    if s.portfolio_analytics_read_key and s.portfolio_supabase_url:
        engagement_service = PortfolioEngagementService(
            source=SupabaseEngagementAdapter(
                http_client=infra.http_client,
                base_url=s.portfolio_supabase_url,
                read_key=s.portfolio_analytics_read_key,
            ),
            ref_prefix=s.portfolio_ref_prefix,
        )
```

  passed as `engagement_service=engagement_service` to the provider (provider param optional, default None; getter returns it). Extend `_Settings` in test_bootstrap with `portfolio_analytics_read_key = ""`; add tests: key unset → `get_engagement_service() is None`; key+url set → not None.
- Service tests: ref parsing (prefix match / foreign ref → None), sort order, source exception → [].
- Route tests: unconfigured → `{"configured": false, "visits": []}`; configured fake service → visits serialized.
- **Commit:** `feat(portfolio): engagement endpoint`.

---

### Task 4: Frontend — application chip + analytics card

**Files:** modify `frontend/src/app/core/services/portfolio.service.ts` (+spec) adding `engagement()`; create `pages/profile/models/portfolio-engagement.model.ts` (`PortfolioVisit` + `EngagementResponse` interfaces, snake_case fields matching backend); application-detail chip; analytics card. READ the existing structures first: `pages/applications/application-detail.component.{ts,html}` (where status/header info renders — put the chip near the header) and `pages/analytics/analytics.component.{ts,html}` (how cards are laid out).

- `portfolio.service.ts`: `engagement(): Observable<EngagementResponse>` GET `/portfolio/engagement`. Spec test.
- **Application detail chip**: on init (application id known), call `engagement()` once (`takeUntilDestroyed`); find the visit whose `application_id === this.applicationId` (however the component exposes it — read it); when found render near the header:

```html
@if (portfolioVisit(); as visit) {
  <span class="portfolio-visit-chip" [title]="'First seen ' + (visit.first_seen | date: 'medium')">
    👀 Portfolio visited — {{ visit.page_views }} page views · last {{ visit.last_seen | date: 'mediumDate' }}
    @if (visit.cv_downloads > 0) { · {{ visit.cv_downloads }} CV downloads }
  </span>
}
```

  Hidden when `configured` false or no matching visit (signal stays null). Spec: flush a response containing the matching visit → chip text appears; empty response → no chip.
- **Analytics card**: a small "Portfolio engagement" card listing up to 10 visits (most recent first): application_id short form (or full ref when application_id null), page_views, cv_downloads, last_seen, country/organization when present. Render the card ONLY when `configured && visits.length > 0`. Follow the page's existing card markup conventions. Spec: card renders rows from a flushed response; absent when unconfigured.
- Full `npm test` + `npx ng lint` clean.
- **Commit:** `feat(portfolio): engagement chip and analytics card`.

---

### Task 5: Verification + smoke + stacked PR

- Backend full suite + ruff; frontend tests + lint.
- Live smoke (key NOT configured — expected for now): `GET /portfolio/engagement` with auth → `{"configured": false, "visits": []}`; app boots clean. THEN, if `PORTFOLIO_ANALYTICS_READ_KEY` is present in `.env` at smoke time, also verify the configured path against the real Supabase (visits may legitimately be empty — assert configured: true and no 5xx).
- Push `feat/portfolio-engagement`; PR base `feat/network-linkedin`, title `feat(portfolio): engagement readback (Phase 5)`; body: RLS rationale for the service key, activation instructions (paste key into .env), failure semantics, smoke evidence; Claude Code footer.

## Self-review notes (applied)
- Spec Part D fully covered; the "separate read key" decision is now grounded in the verified RLS (`auth.uid() IS NOT NULL` on visitor_session).
- No migration, no new module — everything rides the portfolio context.
- Endpoint is read-only and cheap (2 outbound queries) — not rate-limited (consistent with other GET accessories), auth-gated by the router.

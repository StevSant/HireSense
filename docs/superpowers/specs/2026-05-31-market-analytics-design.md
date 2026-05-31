# Analytics & Market Insight — Design

**Date:** 2026-05-31
**Status:** Design proposed — supersedes the concept stub [2026-05-31-market-analytics-concept.md](2026-05-31-market-analytics-concept.md). Brainstormed and approved; pending its own implementation plan.
**Depends on:** the tracking context (status changes), ingestion corpus (`ingested_jobs`), profile context (skills/summary), the vector store + embedding adapter, and the existing `/dashboard` frontend shell. Builds on Phase 2 tracking (status changes are already first-class).

## Problem

HireSense holds rich data it never reflects back to the user: their own application pipeline and a large normalized job corpus. Two analytics surfaces are missing:

1. **Personal funnel** — application → response → interview → offer rates, time-in-stage, conversion.
2. **Market intelligence** — in-demand skills, salary ranges, remote mix, posting trends — plus a **skill-gap** view (profile vs market) and a **personalized target-salary band** ("what salary can I aim for, given my CV?").

All three live on one dashboard.

## Goals

1. A funnel built on **accurate** per-transition data (time-in-stage, real conversion), not just current-status snapshots.
2. Market intel from the corpus: top skills, remote mix, posting trends, best-effort salary distribution.
3. A skill-gap view (what the market wants that the profile lacks, ranked by demand) and a target-salary band derived from jobs that match the candidate.
4. One dashboard page; reuse existing data; no new outbound infra; single-user scale.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | All three surfaces (funnel + market + skill-gap, incl. target salary) on one dashboard |
| Funnel data | A **status-history table**, written **transactionally** in tracking (not via the event bus) so no transition is lost; existing apps seeded by a backfill |
| Conversion definition | Based on the set of statuses an app has **ever** held (history rows); conversion = reached(N+1) / reached(N); `accepted`/`rejected` terminal |
| Market metrics | Top skills, remote/hybrid/on-site mix, posting trend, salary distribution (best-effort). **No seniority** (not stored). |
| Target salary | **Embedding similarity**: profile embedding × job embeddings via the vector store; median + p25–p75 over similar, salaried, open jobs |
| Skill-gap | **Normalized literal + frequency**: normalize/alias skills, rank market skills the profile lacks by corpus demand |
| Compute | **On-the-fly + short TTL cache** (~5 min) for the heavy results (salary distribution, target band); no schema change beyond the history table; no cron |
| Charts | **Hand-rolled CSS/SVG** (no charting dependency) |
| Code location | New read-only **`analytics` bounded context**; the status-history table is owned by **tracking** |

## Architecture

### 1. Status-history table (owned by tracking)

New table **`application_status_history`**:

| column | type | notes |
|---|---|---|
| `id` | UUID PK | |
| `application_id` | UUID, indexed | the tracked application |
| `from_status` | varchar(20), nullable | null on the seed/creation row |
| `to_status` | varchar(20) | |
| `changed_at` | timestamptz, default now() | |

- **Write path:** `TrackingService.update_status` already computes `previous` vs new (Phase 2). When they differ, the tracking repository writes the application **and** inserts a history row in the **same unit of work**. On application creation (`SAVED`), insert a seed row `from=None → to=saved`. The event bus is untouched (the preference subscriber still consumes `TrackingStatusChangedEvent` for taste); history is a synchronous, tracking-owned write so a handler failure can never drop a transition.
- **Backfill:** an Alembic migration creates the table and seeds **one row per existing tracked application** (`from=None → to=current_status`, `changed_at = applied_at or created_at`).
- **Read interface:** tracking exposes a `StatusHistoryReadPort` (e.g. `list_history() -> list[StatusTransition]` / `history_for(application_id)`); the analytics funnel consumes this port (the table stays tracking-owned; analytics depends only on the interface).

### 2. The `analytics` bounded context (read-only)

`backend/src/hiresense/analytics/` — `domain/`, `infrastructure/`, `api/`. One responsibility per unit:

**Pure domain helpers (no I/O):**
- **`SalaryParser`** — `parse(raw: str) -> ParsedSalary | None` yielding `{min, max, currency, period}`. Handles `$`/`€`/`£`, `k` suffixes, ranges (`100k–120k`), and periods (hourly/monthly/annual). Period normalization to annual: hourly ×2080, monthly ×12, annual as-is. Returns `None` on unparseable input.
- **`SkillNormalizer`** — `normalize(skill: str) -> str`: lowercase + trim + a small alias map (e.g. `react.js`→`react`, `k8s`→`kubernetes`, `js`→`javascript`). Shared by skill frequency + skill-gap.

**Query services (read-only):**
- **`FunnelService`** — from the status-history read port: per-stage *reached* counts, conversion rates (reached(N+1)/reached(N)), median time-in-stage (median of consecutive `changed_at` diffs per app), and the current-status distribution. Stages: `saved → applied → interviewing → offered → accepted`, with `rejected` as a terminal outcome tracked separately.
- **`MarketIntelService`** — over `ingested_jobs` where `status='open'`: top normalized skills (count + %), remote-modality mix, posting trend (count per ISO week over `posted_date`), and salary distribution via `SalaryParser` (grouped by currency; report the dominant currency's distribution + counts of other-currency / unparsed rows).
- **`SkillGapService`** — normalized market skills **not** present in the profile, ranked by corpus frequency; each gap carries its share ("in N% of postings"). Reads profile skills (via `ProfileService.get_for_language`) + corpus.
- **`TargetSalaryService`** — embed the profile (summary + skills, reusing the embedding adapter the `SemanticPreRanker` uses) → `vector_store.search(embedding, top_k)` → for those similar, open, salaried jobs parse salaries → median + p25–p75 band + sample size, in the dominant currency. Returns an explicit `insufficient_data` state when fewer than ~5 parseable salaried matches exist or when `vector_store` is `None`.

**Read repositories (`infrastructure/`):** `CorpusAnalyticsRepository` — aggregation SQL over `ingested_jobs` (skills, remote_modality, posted_date histogram, salary rows). The funnel reads through tracking's `StatusHistoryReadPort`.

**TTL cache:** a small `TtlCache` wraps the two heavy results (`MarketIntelService` salary distribution and `TargetSalaryService` band) for ~5 minutes; keyed per result. Time-based invalidation only.

**API (`/analytics`, all auth-required):** four focused GETs so the frontend loads/caches each independently:
- `GET /analytics/funnel` → stage reached-counts, conversion rates, time-in-stage, current distribution.
- `GET /analytics/market` → top skills, remote mix, weekly trend, salary distribution (+ currency/coverage metadata).
- `GET /analytics/skill-gap` → ranked missing skills (+ demand %), and a neutral state when no profile.
- `GET /analytics/target-salary` → median + p25–p75 band + sample size + currency, or `insufficient_data`.

**Bootstrap:** `build_analytics(infra, profile_service, status_history_read)` wired in `main.create_app()` after tracking + profile are built; reads `infra` for `sync_session_factory`, `vector_store`, `embedding`, `settings`. Settings additions (config + `.env.example`): `analytics_cache_ttl_seconds` (default 300), `analytics_target_salary_top_k` (default 50), `analytics_target_salary_min_sample` (default 5).

### 3. Frontend (dashboard analytics page)

New lazy route **`/dashboard/analytics`** (sibling of `/dashboard/matching` etc.) + a nav entry. Standalone, OnPush, signals, `environment.apiUrl`, auth interceptor.

- **`AnalyticsService`** (`core/services/analytics.service.ts`, root-injectable): `funnel()`, `market()`, `skillGap()`, `targetSalary()` → the four endpoints.
- **Models** (one per file, `pages/analytics/models/`): `FunnelMetrics`, `MarketIntel`, `SkillGap`, `TargetSalary`.
- **Page** `analytics.component` — loads the four independently; each section owns its loading / error / empty state so a slow salary parse doesn't block the funnel.
- **Hand-rolled chart components** (standalone, OnPush, reusable, no deps):
  - `bar-chart` — horizontal CSS bars + labels/% (top-skills, skill-gap, remote-mix).
  - `funnel-chart` — stage bars with reached-counts, conversion %, and median time-in-stage between stages.
  - `trend-line` — inline SVG `<polyline>` for postings-per-week.
  - `salary-band` — market min/median/max bar overlaid with the user's target band (p25–p75 + median) and sample size.
- **Section cards:** ① Your funnel ② Target salary (your band vs market) ③ Market (top skills + remote mix + posting trend + salary distribution) ④ Skill gap.

## Error handling & edge cases

- **Salary multi-currency:** group by currency; report the dominant currency's distribution/band, surfacing other-currency + unparsed counts. Unparseable rows excluded and counted.
- **Target band insufficient:** `< analytics_target_salary_min_sample` parseable salaried matches, or `vector_store is None` → explicit `insufficient_data` state (with the count); the other three surfaces are unaffected.
- **No profile / no skills:** skill-gap and target-salary return neutral "upload a CV" states.
- **Fresh funnel:** post-backfill every app has ≥1 seed row, so the current distribution always renders; time-in-stage shows "—" for apps with <2 rows.
- **Empty corpus:** market/skill-gap render neutral empty states.
- **Cache:** per-result, time-based TTL only; a profile/corpus change reflects within the TTL window.
- **Auth:** all endpoints require auth (personal/local data) via the existing interceptor.

## Testing

- **Backend unit:** `SalaryParser` (many real formats + junk → None, period normalization, multi-currency); `SkillNormalizer` (case/alias collapse); `FunnelService` (reached-counts, conversion, time-in-stage from synthetic history incl. terminal states); `MarketIntelService` (frequency/mix/weekly-trend/salary over a fake corpus, currency grouping); `SkillGapService` (gap ranking, profile-overlap exclusion, empty-profile state); `TargetSalaryService` (band from a fake vector search + salaries; insufficient-data + no-vector-store paths).
- **Backend integration:** a PATCH status change writes a `from→to` history row in the same transaction; the backfill migration seeds one row per existing app; the four `/analytics/*` endpoints return correctly-shaped data over real SQLite with a seeded corpus/history; the TTL cache returns the cached result on a second call within the window.
- **Frontend:** `AnalyticsService` URL/shape tests (HttpTestingController); each chart component renders bars/polyline from inputs; the page shows per-section loading/error/empty states.

## Out of scope (future)

Seniority mix (not a stored corpus field — would need inference); persisted/normalized salary columns at ingestion (chose on-the-fly + cache); materialized rollups + cron; multi-user aggregation; embedding-based semantic skill-gap (chose normalized-literal); charting-library-backed interactive charts.

## Implementation sequencing note

Though one spec, the plan can phase as: (1) tracking status-history table + transactional write + backfill + read port; (2) the `analytics` context with `SalaryParser`/`SkillNormalizer` + the four services + endpoints + TTL cache + bootstrap; (3) the frontend route, service, chart components, and section cards. Each phase is independently testable.

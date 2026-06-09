# Profile-Aware Analytics Dashboard — Design

**Date:** 2026-06-09
**Status:** Approved (brainstorming)
**Scope:** Improve the Analytics page — both UI and logic — to be a profile-aware
dashboard organised around three goals the user picked: **benchmark/negotiate
pay**, **track my performance**, and **focus my search**. (Skill-gap stays as-is;
"decide what to learn" was not prioritised.)

## Problem

Today's Analytics page is a flat 4-card grid (Funnel, Target salary, Market,
Skill gap). Two issues:

1. **Under-surfaced logic.** The funnel service already computes per-stage
   conversion rates and median time-in-stage, and target-salary already does the
   profile→embed→ANN→percentile band — but the UI shows only a fraction of it.
2. **Not personalised enough / not goal-organised.** The user wants comp
   benchmarking against *their* profile and pipeline, real performance metrics,
   and where to focus their search — presented as a coherent dashboard, not four
   unrelated cards.

## Architecture

Stays in the existing `analytics` bounded context (hexagonal: `api → domain ←
infrastructure`, facade `AnalyticsService`). No new module. The frontend
`analytics.component` is restructured from a flat grid into a **headline KPI
strip + three goal sections** (Pay / Performance / Focus), reusing the existing
chart components (`bar-chart`, `salary-band`, `funnel-chart`, `trend-line`) and
adding a few. Market + Skill-gap are kept as a secondary "Market context"
footer, unchanged in logic.

Analytics gains **read access to tracked applications** (salary + source +
status), wired in `build_analytics`, for the pipeline-vs-market comparison and
source-outcomes. All sections **fail soft** to an "insufficient data" state, as
target-salary does today, and each loads independently so one empty/slow section
never blocks the rest.

## Components

### ① Pay — `CompBenchmark` (enriches target-salary)

New richer model returned by `GET /analytics/comp` (supersedes
`/target-salary`; the old endpoint is removed and the frontend updated):

- **Market band** (existing logic): profile→embed→ANN top-K → parse salaries →
  `currency`, `p25/median/p75_annual`, `sample_size`, `insufficient_data`.
- **By-seniority bands**: bucket the ANN-matched jobs via the ingestion seniority
  detector (`detect_seniority(title, description)`) → median annual per level
  (`intern/junior/mid/senior/lead`), each with its sample size. Levels below
  `min_sample` are omitted.
- **Your pipeline**: parse salaries from the user's *tracked* applications →
  `your_median_annual` (+ sample) in the dominant currency, for an
  above/below-market read. Null when no tracked app has a parseable salary.
- **Suggested ask range**: `[median_annual, p75_annual]` of the market band
  (null when `insufficient_data`).

Implemented by extending `TargetSalaryService` (rename → `CompBenchmarkService`)
to also accept tracked-application salary strings + reuse the seniority detector;
the salary parser and ANN path are unchanged.

### ② Performance — enriched funnel + source outcomes

- **Surface existing funnel data**: the `funnel-chart` component renders the
  already-computed `conversion_from_prev` and `median_days_in_stage` per stage.
- **Headline rates**: `apply→interview %` and `interview→offer %` derived from
  the funnel stages (no new backend — computed in the facade or frontend).
- **Outcomes by source** (new): join tracked applications to their job's
  `source`; for each source report applications count and reached-interview rate.
  Returned as a new field on the funnel response (`by_source: list[...]`) or a
  sibling `/analytics/performance` payload — **decision: add `by_source` to the
  funnel response** to keep one performance call.
- **Avg match score of tracked apps**: a point KPI (no historical store exists,
  so no time-series trend — explicitly out of scope).

### ③ Focus — `SearchFocus` (new, profile-aware)

`GET /analytics/focus`, reuses profile→embed→ANN top-K open jobs (same path as
comp), excludes `status=closed` and `quality != ok`, then aggregates from a new
corpus read `rows_for_ids(ids)` (title/company/location/posted_date/
remote_modality/quality):

- **best_fit_companies**: top companies among matches (name, count, avg score).
- **best_fit_roles**: top normalised titles among matches (title, count, avg
  score). Title normalisation reuses/extends the existing skill normaliser
  approach or a light title cleaner.
- **location_fit**: share of matches that are remote, and share matching the
  user's country (from profile/strict-location data when available).
- **fresh_fit_count**: matches with `posted_date` within
  `analytics_focus_fresh_days` (new config, default 14).

Fails soft to `insufficient_data` when no vector store / empty profile / no
matches (mirrors comp).

### Headline KPI strip

Derived from the three payloads (frontend composition, no new endpoint): target
**median**, **apply→interview %**, **fresh-fit count**, **best-fit company
count**. Each tile degrades to "—" when its source is insufficient.

## API surface

| Endpoint | Change |
|---|---|
| `GET /analytics/comp` | **new**, replaces `/target-salary`; returns `CompBenchmark` |
| `GET /analytics/funnel` | **enriched**: adds `by_source` + the existing rate/time fields are now consumed |
| `GET /analytics/focus` | **new**; returns `SearchFocus` |
| `GET /analytics/market` | unchanged |
| `GET /analytics/skill-gap` | unchanged |

All under the existing `require_auth` router.

## Frontend

Restructure `analytics.component` into:

- `kpi-strip` (new) — 4 stat tiles.
- **Pay** section — `comp-benchmark` card (new): market band (reuse
  `salary-band`), by-seniority bars (reuse `bar-chart`), pipeline-vs-market line,
  suggested ask range.
- **Performance** section — enhanced `funnel-chart` (show rates + days) +
  source-outcomes (`bar-chart`).
- **Focus** section — `search-focus` card (new): best-fit companies/roles lists,
  location-fit, fresh count.
- **Market context** footer — existing Market + Skill-gap cards, unchanged.

New models: `comp-benchmark.model.ts`, `search-focus.model.ts`,
`source-outcome.model.ts`. Reuse existing chart components throughout.

## Configuration (no hardcoded values)

- `analytics_focus_fresh_days: int = 14` — freshness window for fresh-fit count.
- Reuse existing `analytics_target_salary_top_k`, `_min_sample`,
  `analytics_cache_ttl_seconds`, `analytics_corpus_sample_cap`.
- New settings added to `config.py` + `.env` + `.env.example` with comments.

## Testing

- **Backend (pytest, Postgres-free):** unit tests for the by-seniority split,
  pipeline-vs-market comparison, focus aggregation (best-fit companies/roles,
  location fit, fresh count), and source-outcomes — with stub embedding /
  vector-store / corpus / tracking reads, mirroring existing analytics tests.
  Fail-soft paths (no vector store, empty profile, insufficient sample) covered.
- **Frontend (Vitest):** specs for `kpi-strip`, `comp-benchmark`,
  `search-focus`, and the enriched `funnel-chart`.

## Non-goals

- Match-score / salary trend over time (no historical store; would need a new
  time-series table — out of scope).
- Skill-gap ROI ranking (not prioritised; skill-gap card stays as-is).
- Ghost-job detection, external salary data sources, or cross-user benchmarking.
- Re-computing analytics on write; everything stays read-only aggregation with
  the existing TTL cache.

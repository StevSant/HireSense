# Sorting & Filtering Across List Views — Design

**Date:** 2026-06-07
**Status:** Approved (brainstorming)
**Scope:** Add user-controllable sorting (and, where useful, filtering) to the
list/table views across HireSense. Triggered by the ingestion page lacking
column sorting (e.g. by publication date); broadened to "anywhere we'd benefit."

## Problem

Most list/table views in the app render data in insertion order (or a single
hardcoded order) with no way for the user to reorder or narrow it. The
ingestion page has a minimal sort dropdown (`match_desc` / `date_desc` only)
and a source filter; everything else (Applications, Tracking, Interview
Stories, Cover Letter library/templates, Admin usage tables, Autohunt, Outreach
events) is fixed-order with little or no filtering.

## Core architectural decision: client-side vs server-side

The deciding factor is **whether the list is paginated on the server**:

- **Server-side paginated** → sorting/filtering MUST happen on the server,
  because the client only holds one page and cannot order the full result set.
  Endpoints: `GET /ingestion/jobs` (page/page_size), `GET /autohunt/digests`
  (limit), `GET /admin/usage/recent-calls` (limit/offset).
- **Bare lists loaded fully into the client** → sorting/filtering happens
  **entirely client-side** over the already-loaded array. Zero backend change.
  Views: Applications, Tracking, Interview Stories, Cover Letter Library,
  Cover Letter Templates, Admin Usage Breakdown, Outreach events.
- **Skip (YAGNI)** — tiny or aggregate views where sorting adds no value:
  Preference weights, Outreach nudges, Profile list, all Analytics aggregates.

## Two reusable foundations

### Frontend — shared sortable-table + filter pattern

Used by every list view, client- or server-side. Lives under
`frontend/src/app/core/` (the project's home for cross-cutting code) — e.g.
`core/components/sortable-header/` and `core/utils/` — so it is reusable across
pages.

1. **`createSortState<F>(initialField, initialDir)`** — a signal helper holding
   `{ field, dir }` with a `toggle(field)` method: clicking the active field
   flips direction; clicking a new field selects it with that field's default
   direction (desc for numeric/date fields, asc for text). Exposes the current
   sort as a `field_dir` token string for server endpoints.
2. **`SortableHeaderComponent` / `appSortHeader` directive** — renders a
   clickable `<th>` with a ▲/▼ indicator for the active column and proper
   `aria-sort` ("ascending" / "descending" / "none"). Emits the field key on
   click; binds to a `createSortState` instance.
3. **`sortItems(items, field, dir, accessors)`** — pure client-side comparator
   util with consistent rules: case-insensitive string compare, null/empty
   values sort to the bottom regardless of direction, numbers and dates
   compared natively. Used by bare-list pages.
4. **Filter-bar pattern** — lightweight, composed per page from existing
   primitives (text `input` + `select`); no heavy generic component. A small
   `filterItems` util for client-side text/equality filtering where helpful.

### Backend — generalized `sort` convention (paginated endpoints only)

1. **Sort resolver in the domain/kernel layer** — a pure function that parses a
   `<field>_<dir>` token, looks the field up in a per-endpoint
   `field → key-or-column` map, validates against a whitelist (unknown →
   endpoint default), and returns `(key, reverse)`. No framework imports; lives
   in `domain`. Generalizes today's `if sort == "match_desc"` chain in
   `ingestion/domain/job_filter.py`.
2. **Repository `ORDER BY`** — for DB-paginated lists, push ordering into the
   SQLAlchemy query in the repository so it is correct across pages (instead of
   ordering only the current page in memory).

The token format `<field>_<dir>` (e.g. `posted_desc`, `title_asc`,
`match_desc`) is shared by frontend and backend. `date_desc` is retained as a
backward-compatible alias for `posted_desc` on the ingestion endpoint.

## Rollout phases

Each phase is an independent plan + PR.

### Phase 1 — Foundation + Ingestion (the original ask)

- Build the frontend shared pattern (items 1–4 above) with unit specs.
- Build the backend sort resolver; refactor `ingestion/domain/job_filter.py` to
  use it; extend allowed sort fields to `match, posted, title, company,
  location, source` × `asc, desc`; keep `date_desc` alias; invalid → default
  `match_desc`.
- `ingestion/api/routes.py`: validate `sort` against whitelist; generalize the
  post-scoring re-sort so it re-sorts by match in the chosen direction when the
  field is `match`, and leaves the (already correct) order untouched otherwise.
- Ingestion page UI: replace the sort `<select>` with clickable column headers
  (Match, Title, Company, Location, Source, Posted) using
  `SortableHeaderComponent`; default load = Match desc; keep the "Show closed"
  toggle and existing filters.

### Phase 2 — High-value bare lists (client-side only)

- **Applications** — sortable headers: Title, Company, Status, Match Score,
  Created. Add a status filter `select` + title/company text search.
- **Tracking** — sortable headers: Company, Title, Status, Posted, Applied.
  Keep existing status filter; add company/title text search.
- **Interview Stories** — sortable headers: Title, Competency, Created.
  Keep/extend competency filter.

### Phase 3 — Remaining views

- **Cover Letter Library** — sort by Created/Company/Title; keep search; add
  tone filter. **Cover Letter Templates** — sort by Updated/Name/Tone/Language.
- **Admin Usage Breakdown** (client-side: sort by Cost/Calls/Tokens) and
  **Admin Recent Calls** (server-side via limit/offset: add `sort` param to the
  endpoint + repository ORDER BY; headers for Time/Cost/Latency/Tokens).
- **Autohunt digests** — server-side `sort` (created_at/job_count) on the
  limit-based endpoint.
- **Outreach events** — client-side sort toggle (asc/desc by time) + kind /
  channel filter.

## Testing

- **Frontend (Vitest):** unit specs for `createSortState` (toggle/flip/default
  direction), `sortItems` (null & case handling, each type), and one
  representative table component spec per phase verifying header click → state
  change → reorder/reload.
- **Backend (pytest):** unit tests for the sort resolver (each field×direction,
  invalid→default, alias mapping) and for each touched endpoint's repository
  ordering. Suite stays Postgres-free per project convention.

## Non-goals

- No multi-column / secondary sort.
- No persistence of sort/filter preferences across sessions.
- No new pagination on currently-bare endpoints (they stay fully-loaded;
  client-side handles them). Revisit only if a dataset is shown to grow large.
- No changes to Analytics, Preference weights, Outreach nudges, Profile list.

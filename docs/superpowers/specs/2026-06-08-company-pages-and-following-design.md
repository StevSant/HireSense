# Company pages & following — design

**Date:** 2026-06-08
**Status:** Phase 1 specced; Phase 2 outlined (separate spec to follow)

## Problem

The analytics **Focus — where you fit** card lists best-fit companies and roles
as static text. A user can see "Coderslab.io (13)" but can't act on it — there's
no way to see *which* 13 jobs, how well they match, or to keep an eye on a
company over time.

Today "company" is not a first-class concept: it's only a `company: str` field
on each `NormalizedJob`. There is no company page, no company filter on the jobs
API, and no way to follow a company.

## Goal

Make companies (and roles) in the Focus card actionable:

1. Click a **company** → a dedicated page showing that company's open jobs with
   match scores and a summary header.
2. Click a **role** → the ingestion job list, filtered to that role.
3. (Phase 2) **Follow** a company and revisit followed companies later.

## Scope decomposition

This is two pieces of very different size, delivered as two specs:

- **Phase 1 — Browse (this spec, detailed below).** Read-only. Company filter on
  the jobs API; a dedicated company page; Focus-card company/role links. No
  persistence.
- **Phase 2 — Follow (outlined below; own spec later).** A persisted
  `followed_companies` entity, a save/unfollow control on the company page, and a
  "Companies" sidebar entry → saved-companies list.

Phase 1 ships standalone value and carries no DB/migration risk.

---

## Phase 1 — Browse

### Architecture (Option A)

A dedicated `/dashboard/company/:name` page with a **purpose-built compact job
list**, reusing the existing scored jobs API rather than the inline ingestion
table (which is tightly coupled to sorting, feedback controls, and detail-panel
expansion). The company view is intentionally simpler than the power-user
ingestion list.

### Backend

`backend/src/hiresense/ingestion/`:

1. **`domain/job_filter.py`** — add `company: str | None = None` to
   `JobQueryParams`; in `filter_and_paginate`, add a case-insensitive exact-match
   filter:
   ```python
   if params.company:
       target = params.company.strip().lower()
       filtered = [j for j in filtered if j.company.strip().lower() == target]
   ```
   Exact match (not substring) so "Coderslab.io" doesn't also pull "Coderslab LATAM".
2. **`api/routes.py`** — `GET /ingestion/jobs` gains a `company: str | None = None`
   query param, threaded into `JobQueryParams`.

No new endpoint or module in Phase 1.

**Tests:** unit test for the company filter in `filter_and_paginate` (exact,
case-insensitive, non-matching excluded); endpoint test that `?company=` narrows
the result set.

### Frontend

`frontend/src/app/`:

1. **Route** (`app.routes.ts`) — lazy `company/:name` under the dashboard guard →
   `pages/company/company.component.ts` (`CompanyComponent`).
2. **`pages/company/company.component.*`** (`CompanyComponent`, signals, OnPush):
   - Reads the decoded `:name` route param.
   - On init, fetches the company's jobs via the ingestion service with the new
     `company` filter, for **both** tabs (`boards` + `portals`), `page_size` large
     (e.g. 100 — a single company's open-job count is small once filtered),
     `include_closed=false`. Merges the two result arrays and de-dupes by job id.
   - Computes the **summary header** client-side from the merged jobs: total open
     jobs, count with a match score, average match % (over scored jobs), top
     locations, remote share.
   - Renders: header (company name, summary stats, breadcrumb back to Analytics)
     + a compact **job list** — each row: title (links to the job's
     detail/matching view, following the existing `?job_id=` pattern), a match-%
     badge, location, source, posted date. Sorted by match score desc.
   - Loading / empty ("No open jobs for this company right now.") / error states.
3. **Focus-card links** (`pages/analytics/components/search-focus/`):
   - Best-fit **company** labels become
     `routerLink="/dashboard/company/<encodeURIComponent(label)>"`.
   - Best-fit **role** labels become links to `/dashboard/ingestion` with
     `queryParams: { keyword: label }`.
   - Import `RouterLink`; style links as subtle (accent on hover), not loud.
4. **Ingestion page** (`pages/ingestion/ingestion.component.ts`) — on init, read a
   `keyword` query param (extending the existing `job_id` query-param handling)
   and pre-fill the keyword filter so role links land pre-filtered.
5. **Ingestion service** (`core/services/`) — add `company?: string` to the
   `JobFilters` model and thread it into the `queryJobs` HTTP params (`keyword`
   is already supported).

**Specs:** `CompanyComponent` (renders header + list from a mocked service;
empty and error states); `search-focus` spec asserts the company link href and
the role link's `keyword` query param.

### Data flow

```
Focus card (company click)
  → router → /dashboard/company/:name
  → CompanyComponent
  → IngestionService.queryJobs({ company }) for tab=boards AND tab=portals
  → merge + dedupe by id
  → compute summary + render header + compact job list

Focus card (role click)
  → /dashboard/ingestion?keyword=<role>
  → IngestionComponent reads keyword → pre-fills filter → existing job list
```

### Decisions & known limitations

- **Company identity = exact, case-insensitive `company` string.** The same
  company spelled differently across sources (e.g. "Coderslab" vs "Coderslab.io")
  counts as separate companies. Acceptable for MVP; a normalization/aliasing pass
  is out of scope.
- **Summary is computed client-side** from the fetched jobs — no new aggregation
  endpoint in Phase 1. Safe because the company filter reduces the set to a
  handful of jobs.
- **Match scores are already profile-aware** and recomputed per request by the
  existing `/ingestion/jobs` scoring pipeline; the company page inherits them.
- **"Matching"** in the header = jobs with a non-null `match_score`; the average
  is taken over those.

### Out of scope for Phase 1

Following/persistence, saved-companies list, the sidebar "Companies" entry, role
or location filters beyond the existing `keyword`, company-name normalization.

---

## Phase 2 — Follow (outline only; separate spec)

- **Entity:** `followed_companies` table — `id`, `company` (name), optional
  `source`, `created_at` — global / single-user, mirroring `tracked_applications`
  (no user FK). New ORM (registered in `infrastructure/registry.py`), domain
  model, port, repository, service, API routes, and an Alembic migration.
- **Company page:** a Save / Following toggle that calls the follow endpoints.
- **Saved companies:** a "Companies" sidebar nav item → a saved-companies list
  page (cards per followed company with a mini summary, linking to the company
  page).

These get their own spec → plan → implementation cycle after Phase 1 lands.

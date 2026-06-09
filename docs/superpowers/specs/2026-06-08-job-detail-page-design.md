# Job detail page — design

**Date:** 2026-06-08
**Status:** Specced

## Problem

A job's full detail — including the heavy **deep analysis** (verdict, dimension
bars, matched/missing skills, pros, cons, recommendations, narrative) — is
crammed into a modal/overlay panel (`JobDetailPanelComponent`) opened from the
ingestion list. The overlay is overcharged: the deep analysis is a large,
scroll-heavy block squeezed into a transient panel, and there's no stable,
deep-linkable home for a job's full detail.

## Goal

Give a job a **dedicated, complete detail page** that has room for the full
analysis, and **slim the panel** by moving only the heavy deep-analysis block out
of it. The quick-peek panel stays useful for in-list browsing; the page is the
rich, shareable, deep-linkable surface.

## Architecture

Frontend-only. The backend already exposes everything needed:
`GET /ingestion/jobs/:id` (job) and `GET /ingestion/jobs/:id/analysis` (Tier-2
deep analysis, cache-backed). Reuse the existing `DeepAnalysisComponent` and
`parseJobDescription` lib; extract the description rendering into a shared
component so the panel and the page don't duplicate it.

### New: `JobDetailComponent` (page)

- **Location:** `frontend/src/app/pages/job/job.component.*`
- **Route:** `/dashboard/job/:id` (lazy, under the dashboard auth guard).
- **Behaviour:**
  - Reads `:id`; fetches the job via `IngestionService.getJob(id)`.
  - **Auto-loads** the deep analysis on open via `IngestionService.getJobAnalysis(id)`
    (cache-backed: first visit runs the Tier-2 LLM call, cached thereafter). Shows
    loading / error (with retry) states for the analysis section independently of
    the job header.
  - Loading / error states for the job fetch itself.
- **Content (complete job view):**
  - **Header:** title; **company name linking to `/dashboard/company/:name`**
    (the page built in the previous feature); score pill (reusing
    `formatScorePercent` + `scoreColor`); key facts — location, salary, source,
    posted date.
  - **Full description** via the shared `JobDescriptionComponent`.
  - **Deep analysis** via the existing `DeepAnalysisComponent`.
  - **Actions:** Track (→ `ApplicationsService.createFromJob`, mirroring the
    ingestion list's track flow), and navigation to Matching / Optimization /
    Interview (`/dashboard/{matching,optimization,interview}?job_id=:id`), the
    same targets the panel uses today.

### Changed: `JobDetailPanelComponent` (slimmed)

- **Keep:** header, key facts, the job **description**, feedback controls, Track.
- **Remove:** the collapsible deep-analysis block and all of its
  state/handlers (`analysis`, `analysisExpanded`, `analysisLoading`,
  `analysisError`, `toggleDeepAnalysis`, `loadAnalysis`, `retryAnalysis`, and the
  `DeepAnalysisComponent` import).
- **Add:** a prominent **"View full analysis →"** link/button that navigates to
  `/dashboard/job/:id` (and closes the panel).

### New (shared): `JobDescriptionComponent`

- **Location:** `frontend/src/app/pages/ingestion/components/job-description/`
- Takes the raw `description: string` as input, runs `parseJobDescription`
  internally, and renders the parsed sections (with the existing raw-text
  fallback when there are no structured sections).
- Used by **both** the slimmed panel and the new page — removes duplication.
- The description-parsing/rendering markup currently inline in the panel template
  moves here verbatim; the panel composes `<app-job-description [description]="…">`.

### Entry points

- **Ingestion list "View"** → slim panel (unchanged) → **"View full analysis →"** →
  `/dashboard/job/:id`.
- **Company page** job titles → change from `?job_id=` (which opened the panel in
  ingestion) to **`/dashboard/job/:id` directly** (the company page has no panel;
  the page is the correct target). [Updates `company.component.html`.]
- Matching / optimization / interview deep-links unchanged.

## Data flow

```
Ingestion list → View → slim panel → "View full analysis →"
  → /dashboard/job/:id → JobDetailComponent
       → IngestionService.getJob(id)            (header + description)
       → IngestionService.getJobAnalysis(id)    (auto, cache-backed → deep analysis)

Company page job title → /dashboard/job/:id (direct)
```

## Decisions

- **Panel keeps the description**; only the deep analysis moves to the page
  (confirmed). The panel stays a genuine quick-peek; the analysis is the one heavy
  thing that was overcharging it.
- **Auto-load the analysis** on the page (confirmed) — cache-backed, so it's a
  network call only on a true cache miss.
- **No backend changes** — existing endpoints suffice.
- **DRY:** description rendering extracted to a shared component rather than
  duplicated between panel and page.

## Testing

- `JobDetailComponent` spec: mocks `IngestionService` (`getJob`, `getJobAnalysis`,
  `getCachedAnalysis`) and `ApplicationsService`; `ActivatedRoute` with an `id`
  param. Asserts: header renders job fields; company links to the company page;
  the analysis section renders once loaded; job-fetch error state; analysis error
  state.
- `JobDescriptionComponent` spec: renders structured sections for a sectioned
  description and falls back to raw text otherwise.
- `JobDetailPanelComponent` spec (if present) updated: deep-analysis block gone,
  "View full analysis →" link present and pointing at `/dashboard/job/:id`.
- Company-page change verified by its existing spec / a new assertion that job
  titles link to `/dashboard/job/:id`.

## Out of scope

- Any change to the Tier-2 analysis backend, the matching/optimization/interview
  pages, or the analysis content itself.
- Following/saving jobs (separate from companies).
- Redesigning the deep-analysis visuals — `DeepAnalysisComponent` is reused as-is
  (it already renders well; it just gets more room on the page).

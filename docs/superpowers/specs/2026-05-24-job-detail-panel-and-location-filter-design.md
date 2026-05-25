# Job Detail Panel Layout Fix + Location Preference Filter — Design

**Date:** 2026-05-24
**Scope:** Frontend (Angular) + Backend (FastAPI)
**Status:** Approved

## Problem

Two issues observed on the Ingestion page:

1. **Job detail side panel layout is broken.** When opening a job, the panel's action buttons (`View Original`, `Track`) are pushed below the viewport and become unreachable. The description has its own `max-height: 300px` internal scroll that competes with the panel-level `overflow-y: auto`, producing inconsistent behavior depending on content length.

2. **Jobs marked as `Remote` in our system can be country-restricted on the source platform.** Example: a getonbrd job normalized to `"Remote (Remote)"` actually requires the applicant to be in a specific region. When the user opens the source URL, the platform shows "Your country doesn't match the job's location." The user has no way to express "only show me jobs I can apply to from my location."

## Goals

- Fix the panel layout so all sections remain accessible regardless of content length.
- Let the user enter their location and opt into strict location matching, applied uniformly across all job sources.
- Preserve current behavior as the default (strict matching is opt-in).

## Non-Goals

- Per-adapter location parsing improvements (e.g., extracting structured `restricted_countries` from raw source data). The filter operates on the normalized `location` string only.
- Geo-coding or country-code normalization. Plain substring match on user input.
- Changing the source URL behavior or surfacing the platform's own country restrictions inside our UI.

---

## Section 1 — Job Detail Panel Layout

### Current structure

`job-detail-panel.component.html` / `.scss`:

- `.panel-overlay` — `position: fixed; inset: 0; display: flex; justify-content: flex-end;`
- `.panel` — flex child stretched to 100vh; `overflow-y: auto`; `display: flex; flex-direction: column;`
- Sections inside: header, meta grid, source, skills, description (`max-height: 300px; overflow-y: auto;`), actions (`margin-top: auto`)

The competing scroll regions (panel-level + description-level) plus reliance on `margin-top: auto` push actions off-screen when content is tall.

### New structure

Replace the flex-column layout with a CSS grid that defines three explicit rows:

```scss
.panel {
  display: grid;
  grid-template-rows: auto 1fr auto;
  height: 100%;
  overflow: hidden; // outer container does not scroll
}

.panel-header { /* row 1 — sticky at top, no change to visual style */ }

.panel-body {
  overflow-y: auto;
  // contains: meta grid, source, skills, description
}

.panel-actions { /* row 3 — always visible at bottom */ }
```

Template change: wrap meta grid, source, skills, and description in a new `<div class="panel-body">`. Header and actions stay outside it.

Description loses its `max-height: 300px` and inner `overflow-y`. It flows naturally inside the single scrollable `.panel-body`.

### Result

- Header always visible at top.
- Actions always visible at bottom.
- One scroll region in the middle covers all variable-length content.
- No nested scrolls.

---

## Section 2 — Location Preference + Strict-Match Toggle

### Frontend

**`job-filters.component`** gains two new controls:

- **"My location"** — text input (`<input type="text">`). Free-form, e.g. `"Chile"`, `"USA"`, `"Spain"`, `"Latin America"`.
- **"Only show jobs I can apply to"** — checkbox.

**Persistence:** Both values persist in `localStorage` so they survive page refresh and tab close:

- `hiresense.user_location` — string
- `hiresense.strict_location_match` — `"true"` | `"false"`

On component init, read both from `localStorage` and initialize the local filter state. On change, write back to `localStorage` and emit the updated filters.

**`JobFilters` interface** (`core/services/ingestion.service.ts`) gains:

```ts
export interface JobFilters {
  source?: string;
  keyword?: string;
  location?: string;        // existing — job-location keyword search
  skills?: string;
  date_from?: string;
  date_to?: string;
  user_location?: string;   // new — applicant's location
  strict_location?: boolean; // new — enforce location match
}
```

`IngestionService.queryJobs` adds `user_location` and `strict_location` to the `HttpParams` when set. The existing `location` filter (job-location keyword search) is unchanged and orthogonal to the new fields.

**Default state:** `strict_location` defaults to `false`. If the user has never enabled it, behavior is identical to today.

### Backend

**`JobQueryParams`** (`hiresense/ingestion/domain/job_filter.py`) gains:

```python
user_location: str | None = None
strict_location: bool = False
```

**`filter_and_paginate`** gets a new filter step:

```python
if params.strict_location and params.user_location:
    user_loc = params.user_location.strip().lower()
    open_keywords = ("worldwide", "anywhere", "global")
    def is_open(job_location: str) -> bool:
        if not job_location:
            return True
        loc = job_location.lower()
        if any(kw in loc for kw in open_keywords):
            return True
        return user_loc in loc
    filtered = [j for j in filtered if is_open(j.location)]
```

A job passes when **at least one** holds:

1. `job.location` is empty.
2. `job.location` (lowercased) contains any of `worldwide`, `anywhere`, `global`.
3. `job.location` (lowercased) contains `user_location` (lowercased) as a substring.

Otherwise the job is excluded.

**Route binding:** `ingestion/api/routes.py::list_jobs` declares each query param explicitly and constructs `JobQueryParams` by hand. Add `user_location: str | None = None` and `strict_location: bool = False` to the signature and forward them into the `JobQueryParams(...)` call.

### Behavior on the screenshot bug

- Job normalized to `location = "Remote (Remote)"`.
- User sets `user_location = "Chile"`, `strict_location = true`.
- Check: empty? no. Has `worldwide`/`anywhere`/`global`? no. Contains `"chile"`? no.
- Job is excluded. Correct outcome.

### Acknowledged tradeoff

A genuinely worldwide remote job whose `location` field is only `"Remote"` (no `worldwide`/`anywhere`/`global` tokens) will also be excluded under strict mode. The toggle is opt-in; users who want broader results turn it off. This is the explicit purpose of the switch.

---

## Files touched

**Frontend**

- `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.html` — wrap middle sections in `.panel-body`.
- `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.scss` — grid layout, remove description `max-height`.
- `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.html` — add location input + checkbox.
- `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.ts` — wire up localStorage persistence + new emit fields.
- `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.scss` — minor styling for the new controls.
- `frontend/src/app/core/services/ingestion.service.ts` — extend `JobFilters` + `queryJobs` params.

**Backend**

- `backend/src/hiresense/ingestion/domain/job_filter.py` — extend `JobQueryParams`, add filter step.
- `backend/src/hiresense/ingestion/api/routes.py` — surface the new params on the jobs query endpoint (verify Pydantic binding).

## Testing

- **Backend:** unit tests on `filter_and_paginate` covering: empty location, `Worldwide`, `Remote (Remote)` excluded when `user_location="Chile"`, exact country match, mixed case, strict off (no-op).
- **Frontend:** manual verification in the browser — open detail panel with short and long descriptions, confirm header/actions stay fixed; set `user_location="Chile"` + strict ON, confirm `Remote (Remote)` getonbrd jobs disappear; refresh page, confirm settings persist.

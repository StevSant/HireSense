# Job Ingestion Improvements — Design Spec

**Date:** 2026-04-12
**Status:** Approved

## Problem

The Job Ingestion page has several usability and reliability issues:

1. **No source visibility** — Users can't tell where jobs came from or view job details
2. **No source filtering** — Can't filter the table by which board/portal a job came from
3. **No pagination** — 1,100+ jobs dumped in a single table
4. **Confusing UX** — "Fetch Jobs" and "Scan Portals" buttons are unclear in purpose
5. **Broken portals** — 9 of 16 configured portals return 404/401 errors

## Solution Overview

Restructure the ingestion page into two clear tabs with shared filtering, pagination, a job detail panel, and fixed portal configurations.

---

## 1. Page Layout — Two Tabs

### Tab 1: "Job Boards"

Pulls from the 9 public job board sources: Remotive, RemoteOK, Jobicy, Himalayas, HN Hiring, WeWorkRemotely, GetOnBoard, LinkedIn, CSV.

- "Fetch Jobs" button in the tab bar triggers `POST /ingestion/fetch`
- Below: shared filters bar + paginated table + detail panel

### Tab 2: "Company Portals"

Pulls from configured company career pages via Greenhouse/Lever/Ashby APIs.

- **Scan filters section** (above the filters bar): category multi-select, company multi-select, keyword input — these control *what to scan*
- "Scan Portals" button triggers `POST /ingestion/scan-portals` with scan filters
- Below: same shared filters bar + paginated table + detail panel — these filter *what you see* from already-fetched results

Both tabs share the same table component, filters bar, pagination, and detail panel. Only the data source and fetch mechanism differ.

---

## 2. Backend API Changes

### `GET /ingestion/jobs` — Paginated query endpoint

Replaces the current "return all jobs" behavior. Query parameters:

| Parameter   | Type              | Default   | Description                                      |
|-------------|-------------------|-----------|--------------------------------------------------|
| `tab`       | `boards\|portals` | required  | Which source group to query                      |
| `page`      | int               | 1         | Page number                                      |
| `page_size` | int (20,50,100)   | 20        | Items per page                                   |
| `source`    | string (optional) | —         | Filter by specific source name                   |
| `keyword`   | string (optional) | —         | Substring search in title and description        |
| `location`  | string (optional) | —         | Substring match on location                      |
| `skills`    | string (optional) | —         | Comma-separated, filter jobs with any match      |
| `date_from` | date (optional)   | —         | Jobs posted on or after this date                |
| `date_to`   | date (optional)   | —         | Jobs posted on or before this date               |

Response:

```json
{
  "jobs": [NormalizedJob, ...],
  "total": 1109,
  "page": 1,
  "page_size": 20,
  "total_pages": 56
}
```

**Source grouping logic:** Board sources are `remotive`, `remoteok`, `jobicy`, `himalayas`, `hn_hiring`, `weworkremotely`, `getonboard`, `linkedin`, `csv`. Portal sources are `greenhouse`, `lever`, `ashby`. The `tab` parameter filters by this grouping.

### `POST /ingestion/fetch` — unchanged

Triggers pull from all public job boards. Returns `FetchResponse` with count and jobs. After calling, frontend refreshes via `GET /ingestion/jobs?tab=boards`.

### `POST /ingestion/scan-portals` — unchanged

Triggers portal scanning with category/company/keyword scan filters. Returns `ScanResult` with metrics and jobs. After calling, frontend refreshes via `GET /ingestion/jobs?tab=portals`.

### `GET /ingestion/portals` — unchanged

Returns configured portal entries for the scan filter UI.

---

## 3. Data Model Changes

### Backend `NormalizedJob` — add fields

- `platform: str | None` — ATS platform for portal jobs (`greenhouse`, `lever`, `ashby`). `None` for board jobs.
- `categories: list[str]` — category tags from `portals.yml` for portal jobs. Empty list for board jobs.

Fields already present but not exposed to frontend:
- `source_type` — already exists, needs to be included in the API response schema
- `department` — already exists, needs to be included in the frontend model

### Frontend `NormalizedJob` interface — add fields

```typescript
source_type: string;         // "api" | "rss" | "scraper" | "manual"
platform: string | null;     // "greenhouse" | "lever" | "ashby" | null
categories: string[];        // e.g., ["ai-research"]
department: string | null;   // already in backend, missing from frontend
```

### New `PaginatedJobsResponse` model

```typescript
{
  jobs: NormalizedJob[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
```

---

## 4. Filters Bar

Shared component used by both tabs. Single horizontal row with:

| Filter     | Type                | Behavior                                         |
|------------|---------------------|--------------------------------------------------|
| Source     | Multi-select dropdown | Options populated per tab. Boards tab: source names (Remotive, LinkedIn...). Portals tab: company names (Anthropic, Vercel...) |
| Keyword    | Text input          | Debounced 300ms, searches title + description    |
| Location   | Text input          | Debounced 300ms, substring match                 |
| Skills     | Text input          | Comma-separated, debounced 300ms                 |
| Date From  | Date picker         | Triggers on change                               |
| Date To    | Date picker         | Triggers on change                               |
| Clear All  | Button              | Resets all filters                                |

Every filter change resets to page 1 and triggers `GET /ingestion/jobs` with updated params.

---

## 5. Pagination

Below the table:

- **Left:** "Showing 1–20 of 1,109 jobs"
- **Right:** Page size selector (20 / 50 / 100) + Previous/Next buttons + "Page X of Y"
- Changing page size resets to page 1

---

## 6. Job Detail Panel

Slide-out panel from the right side. Opens when clicking a job row. Sections:

### Header
- Job title (large), company name, close button (X)

### Meta Grid (2×2)
- Location, posted date (formatted), salary range, department

### Source Info
- Source badge (color-coded), source type label (API/RSS/Scraper)
- For portal jobs: platform badge + category tags

### Skills
- Displayed as chips/tags

### Description
- Full job description (HTML-stripped, formatted)

### Actions
- "View Original" — opens source URL in new tab
- "Track" / "Tracked" — existing tracking behavior

Panel closes via X button or clicking outside.

---

## 7. Broken Portals Fix

### Approach
1. Research each failing company's current careers page to find actual ATS platform and board ID
2. Update `portals.yml` with correct values
3. Remove companies that have gone fully private (no public API board)
4. Add `enabled: bool` field to `PortalEntry` so broken portals can be disabled without deletion

### Currently failing (9 of 16):
- OpenAI (greenhouse) — 404
- Mistral (greenhouse) — 404
- Cohere (greenhouse) — 404
- LangChain (greenhouse) — 404
- ElevenLabs (ashby) — 401
- Deepgram (greenhouse) — 404
- Retool (lever) — 404
- Weights & Biases (greenhouse) — 404
- n8n (greenhouse) — 404

### Currently working (7 of 16):
- Anthropic, Hugging Face, Stability AI, Scale AI, Pinecone, Vercel, Temporal

---

## 8. Component Architecture

### Frontend Components

- **IngestionComponent** — page shell with tab switching logic
- **JobFiltersComponent** — shared filters bar (source, keyword, location, skills, date range)
- **JobTableComponent** — shared paginated table with column display
- **JobDetailPanelComponent** — slide-out detail panel
- **PaginationComponent** — page size selector + navigation
- **ScanFiltersComponent** — portal tab scan filters (categories, companies, keyword for what to fetch)

### Backend Changes

- **`GET /ingestion/jobs`** — new query params for filtering and pagination
- **`IngestionOrchestrator`** — add filtering/pagination methods to `list_jobs()`
- **`PortalScanner`** — same, add filtering/pagination to stored results
- **`NormalizedJob` schema** — add `platform`, `categories` fields
- **`PaginatedJobsResponse` schema** — new response model
- **`portals.yml`** — fix board IDs, add `enabled` field

---

## 9. Source Badge Colors

Each source gets a distinct color for visual scanning:

| Source         | Background | Text Color |
|----------------|-----------|------------|
| remotive       | teal-50   | teal-600   |
| getonboard     | amber-50  | amber-800  |
| linkedin       | violet-50 | violet-800 |
| himalayas      | pink-50   | pink-800   |
| remoteok       | blue-50   | blue-800   |
| jobicy         | green-50  | green-800  |
| weworkremotely | orange-50 | orange-800 |
| hn_hiring      | red-50    | red-800    |
| greenhouse     | emerald-50| emerald-800|
| lever          | indigo-50 | indigo-800 |
| ashby          | cyan-50   | cyan-800   |

---

## Non-Goals

- No database persistence (stays in-memory for now)
- No real-time job updates or websockets
- No sorting by column (can be added later)
- No export/download functionality
- No job deduplication UI (handled automatically in backend)

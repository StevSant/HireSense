# Portal Scanning — Design Spec

**Date:** 2026-04-06
**Status:** Approved
**Phase:** 1 of 6 (career-ops feature adoption roadmap)

## Overview

Extend the existing ingestion module with three new job board platform adapters — Greenhouse, Lever, and Ashby — enabling HireSense to scan 45+ company career pages via their public APIs. Companies are configured in a YAML registry file, making it easy to add or remove portals without code changes.

## Goals

- Scan company career pages across Greenhouse, Lever, and Ashby ATS platforms
- Ship with a default company list, fully configurable via YAML
- Reuse existing ingestion architecture (adapter pattern, normalizers, dedup, events)
- Manual trigger now, architecture ready for scheduled scanning later
- Prepare for future migration to DB-backed portal configuration

## Non-Goals

- Scheduled/cron scanning (future phase)
- Database-backed portal config (future phase)
- Scraping non-API career pages (HTML scraping)
- Authentication-gated job boards

---

## Architecture

### File Structure

```
backend/src/hiresense/ingestion/
├── adapters/
│   ├── remotive.py              (existing)
│   ├── remoteok.py              (existing)
│   ├── greenhouse_adapter.py    (new)
│   ├── lever_adapter.py         (new)
│   └── ashby_adapter.py         (new)
├── domain/
│   ├── normalizers/
│   │   ├── remotive.py          (existing)
│   │   ├── remoteok.py          (existing)
│   │   ├── greenhouse.py        (new)
│   │   ├── lever.py             (new)
│   │   └── ashby.py             (new)
│   └── services.py              (extend with scan_portals)
├── config/
│   └── portals.yml              (new — company registry)
├── api/
│   ├── routes.py                (extend with POST /scan-portals)
│   └── dependencies.py          (existing)
```

### Dependency Flow

```
routes.py (POST /scan-portals)
  → IngestionService.scan_portals(filters)
    → load portals.yml, filter by category/company
    → group portals by platform
    → fan out to adapters (parallel across platforms, sequential within)
    → normalize via platform-specific normalizer
    → deduplicate against existing jobs
    → publish JobsIngestedEvent
    → return ScanResult
```

---

## Portal Configuration

### File: `backend/src/hiresense/ingestion/config/portals.yml`

```yaml
portals:
  # AI Research Labs
  - name: Anthropic
    platform: greenhouse
    board_id: anthropic
    categories: [ai-research]

  - name: OpenAI
    platform: greenhouse
    board_id: openai
    categories: [ai-research]

  - name: Mistral
    platform: greenhouse
    board_id: mistralai
    categories: [ai-research]

  - name: Cohere
    platform: greenhouse
    board_id: cohere
    categories: [ai-research]

  - name: LangChain
    platform: greenhouse
    board_id: langchain
    categories: [ai-research]

  # Voice Technology
  - name: ElevenLabs
    platform: ashby
    board_id: elevenlabs
    categories: [voice-tech]

  - name: Deepgram
    platform: greenhouse
    board_id: deepgram
    categories: [voice-tech]

  # Development Platforms
  - name: Retool
    platform: lever
    board_id: retool
    categories: [dev-platforms]

  - name: Vercel
    platform: greenhouse
    board_id: vercel
    categories: [dev-platforms]

  - name: Temporal
    platform: greenhouse
    board_id: temporal
    categories: [dev-platforms]

  # LLM Operations
  - name: Weights & Biases
    platform: greenhouse
    board_id: wandb
    categories: [llm-ops]

  # Workflow Automation
  - name: n8n
    platform: greenhouse
    board_id: n8n
    categories: [workflow-automation]
```

### Config Model (Pydantic)

```python
class PortalEntry(BaseModel):
    name: str
    platform: Literal["greenhouse", "lever", "ashby"]
    board_id: str
    categories: list[str] = []

class PortalsConfig(BaseModel):
    portals: list[PortalEntry]
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORTALS_CONFIG_PATH` | `ingestion/config/portals.yml` | Path to portal registry (relative to backend/src/hiresense/) |
| `PORTAL_SCAN_TIMEOUT` | `30` | HTTP timeout per portal in seconds |
| `GREENHOUSE_API_URL` | `https://boards-api.greenhouse.io/v1/boards` | Greenhouse API base URL |
| `LEVER_API_URL` | `https://api.lever.co/v0/postings` | Lever API base URL |
| `ASHBY_API_URL` | `https://api.ashbyhq.com/posting-api/job-board` | Ashby API base URL |

---

## Platform Adapters

Each adapter implements the existing source port interface and calls the platform's public API.

### Greenhouse Adapter

- **Endpoint:** `GET {GREENHOUSE_API_URL}/{board_id}/jobs?content=true`
- **Auth:** None (public API)
- **Response:** JSON array of job objects
- **Key fields:** `title`, `location.name`, `content` (HTML), `absolute_url`, `updated_at`, `departments[].name`
- **Pagination:** `?page=1&per_page=100` — iterate until empty page

### Lever Adapter

- **Endpoint:** `GET {LEVER_API_URL}/{board_id}?mode=json`
- **Auth:** None (public postings API)
- **Response:** JSON array of posting objects
- **Key fields:** `text` (title), `categories.location`, `description` (HTML), `hostedUrl`, `createdAt`, `categories.team`
- **Pagination:** `?skip=0&limit=100` with `hasNext` field

### Ashby Adapter

- **Endpoint:** `POST {ASHBY_API_URL}/{board_id}`
- **Auth:** None (public posting API)
- **Response:** JSON with `jobs[]` array
- **Key fields:** `title`, `location`, `descriptionHtml`, `jobUrl`, `publishedAt`, `departmentName`
- **Pagination:** Not paginated (returns all postings)

---

## Normalizer Mapping

Each normalizer maps platform-specific fields to `NormalizedJobDTO`:

| NormalizedJobDTO field | Greenhouse | Lever | Ashby |
|---|---|---|---|
| `title` | `title` | `text` | `title` |
| `company` | from `portals.yml` entry | from `portals.yml` entry | from `portals.yml` entry |
| `description` | `content` (strip HTML) | `description` (strip HTML) | `descriptionHtml` (strip HTML) |
| `url` | `absolute_url` | `hostedUrl` | `jobUrl` |
| `location` | `location.name` | `categories.location` | `location` |
| `source` | `"greenhouse"` | `"lever"` | `"ashby"` |
| `posted_at` | `updated_at` | `createdAt` | `publishedAt` |
| `department` | `departments[0].name` | `categories.team` | `departmentName` |

HTML stripping uses a shared utility that converts HTML to plain text, preserving paragraph breaks.

**Note:** `NormalizedJobDTO` may need two new optional fields: `posted_at: datetime | None` and `department: str | None`. These should be added if not already present.

---

## API Endpoint

### `POST /api/ingestion/scan-portals`

**Request body (all fields optional):**

```json
{
  "categories": ["ai-research", "voice-tech"],
  "companies": ["Anthropic", "ElevenLabs"],
  "keyword": "engineer"
}
```

- Empty body scans all portals in `portals.yml`
- `categories` — filter portals by category tag
- `companies` — filter portals by company name
- `keyword` — passed as query parameter to APIs that support search (Greenhouse `content` param)

**Response:**

```json
{
  "total_fetched": 45,
  "new": 32,
  "duplicates": 13,
  "jobs": [
    {
      "title": "Senior Backend Engineer",
      "company": "Anthropic",
      "location": "San Francisco, CA",
      "url": "https://boards.greenhouse.io/anthropic/jobs/123",
      "source": "greenhouse",
      "posted_at": "2026-04-01T00:00:00Z"
    }
  ],
  "errors": [
    {
      "portal": "ElevenLabs",
      "platform": "ashby",
      "error": "Request timeout after 30s"
    }
  ]
}
```

### Request/Response Models (Pydantic)

```python
class ScanPortalsRequest(BaseModel):
    categories: list[str] = []
    companies: list[str] = []
    keyword: str | None = None

class ScanError(BaseModel):
    portal: str
    platform: str
    error: str

class ScanResult(BaseModel):
    total_fetched: int
    new: int
    duplicates: int
    jobs: list[NormalizedJobDTO]
    errors: list[ScanError]
```

---

## Error Handling

- **Isolation:** Each portal scanned independently. A failure on one portal does not block others.
- **Timeout:** Configurable via `PORTAL_SCAN_TIMEOUT` env var (default 30s per portal).
- **Error collection:** Failed portals returned in `errors[]` alongside successful results.
- **Rate limiting:** Requests are sequential within each platform (avoid hammering same API host), parallel across different platforms.
- **Retry:** No automatic retries. User can re-trigger scan for failed portals.

---

## Deduplication

- Reuse existing dedup logic: hash of `(url)` or `(title, company)` as fallback.
- Jobs already ingested from Remotive/RemoteOK are deduped against portal scan results.
- Scan response reports `new` vs `duplicates` counts.

---

## Frontend Changes

### Ingestion Page Additions

1. **"Scan Portals" button** — alongside existing "Fetch Jobs" button
2. **Filter controls** (collapsible):
   - Category multi-select dropdown (populated from `portals.yml` categories)
   - Company multi-select dropdown (populated from `portals.yml` names)
   - Keyword text input
3. **Scan summary banner** — shows after scan: "Found 32 new jobs (13 duplicates). 1 portal failed."
4. **Error details** — expandable section showing which portals failed and why
5. **Results** — merge into existing job table with `source` column showing platform name

### New API Calls

```typescript
// ingestion.service.ts
scanPortals(filters: ScanPortalsRequest): Observable<ScanResult>
getPortalConfig(): Observable<PortalEntry[]>  // for populating filter dropdowns
```

### New Backend Endpoint for Config

```
GET /api/ingestion/portals
```

Returns the parsed `portals.yml` so the frontend can populate filter dropdowns without duplicating the company list.

---

## Future Considerations

- **DB-backed config:** Migrate `portals.yml` to a `portals` table, add CRUD API and admin UI
- **Scheduled scanning:** Add a cron trigger that calls `scan_portals()` on an interval
- **Webhook support:** Some ATS platforms support webhooks for new postings
- **Additional platforms:** Wellfound, Workable, RemoteFront, direct HTML scraping

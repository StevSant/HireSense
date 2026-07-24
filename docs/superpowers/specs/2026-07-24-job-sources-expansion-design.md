# Job Sources Expansion — Design

**Date:** 2026-07-24  
**Status:** Specced → Implementing  
**Scope:** Add Indeed, Wellfound, Y Combinator Jobs, Glassdoor, Monster, Dice, and
CrunchBoard to HireSense ingestion; introduce a source-capability registry; improve
normalized metadata, cross-source provenance, per-source health, and frontend source UX.

## Problem

HireSense already ingests a strong set of remote boards and company ATS portals, but
major discovery surfaces used by tech candidates (Indeed, Wellfound, YC Work at a
Startup, Glassdoor, Monster, Dice, CrunchBoard) are missing. Candidates therefore miss
startup-equity roles, tech-contract roles, and aggregator coverage that ATS portals
alone do not provide.

Simply adding seven HTML scrapers would be brittle, ToS-risky, and inconsistent with
HireSense’s ports-and-adapters design. Each platform needs a feasibility-driven
integration method, shared infrastructure for capabilities/health/metadata, and clear
fallbacks when automation is not legitimately available.

## Goals

1. Ship production-quality adapters (or compliant import fallbacks) for all seven
   platforms, wired through existing `JobSourcePort` / bootstrap / config.
2. Capture publicly available platform strengths (Dice skills/contract metadata, YC
   batch/equity/visa, CrunchBoard RSS freshness, Wellfound startup fields via import).
3. Introduce a typed **source capability registry** consumed by backend and frontend.
4. Extend normalized job metadata without breaking stable identity `(bucket, source,
   identity_key)`.
5. Improve cross-source dedup provenance (which sources saw the role) and source-tier
   precedence (direct ATS > company boards > aggregators).
6. Expose per-source health/observability for last run, counts, and errors.
7. Keep one failing source from failing a multi-source run (existing isolation).
8. Document limitations and compliance boundaries honestly.

## Non-goals

- Bypassing Cloudflare/DataDome/login walls or CAPTCHAs.
- Ingesting Glassdoor reviews or any login-gated content.
- Paid third-party scraper SaaS dependencies.
- Replacing the existing stable identity mechanism with a global cross-source primary key.
- Redesigning Discover UI beyond source badges/filters/health/metadata presentation.

## Feasibility matrix (2026-07-24 research)

| Platform | Best legitimate method | Auth | Pagination | Rate limits | Fields of interest | Closure strategy | Risks | Recommendation |
|---|---|---|---|---|---|---|---|---|
| **Indeed** | No public Jobs API (Publisher API deprecated). RSS 404. Search HTML heavily bot-protected. | N/A for read | N/A | N/A | keyword, location, remote, salary, easy-apply, company, apply URL | URL probe if live URLs imported | ToS / bot blocks | **Structured JSONL/CSV import fallback** (`source=indeed`). Live scrape opt-in not shipped. |
| **Wellfound** | No public API; GraphQL session-gated; DataDome on `/jobs`. | Session (not used) | SPA cache ~page | Aggressive | startup stage, team size, funding, salary/equity, visa, skills | URL probe on imported URLs | DataDome | **JSONL import** with rich startup schema. |
| **YC Jobs** | Public Work at a Startup HTML embeds Inertia `data-page` JSON (`jobs[]`). Company pages add equity/visa/experience. `api.ycombinator.com/v0.1/companies` for firmographics. | None | Role pages (`/jobs/role/{role}`) | Polite delays | YC batch, salary, equity, remote, visa, skills, apply URL | URL revalidation (feed/search, not full snapshot) | Markup/Inertia shape drift | **Automated adapter** parsing public embedded JSON + optional company enrichment. |
| **Glassdoor** | Partner API shut down; Cloudflare on job search; reviews login-walled. | N/A | N/A | Aggressive | jobs, salary estimates, company rating/size/industry/HQ (public only) | URL probe if imported | ToS forbids scrapers; reviews gated | **JSONL/CSV import of public job fields only**. No reviews. |
| **Monster** | Historical RSS dead (404). Search returns bot challenge. No public developer API. | N/A | N/A | Aggressive | keyword, location, remote, employment type, salary, apply URL | URL probe if imported | Bot protection | **JSONL/CSV import fallback**. |
| **Dice** | **Official MCP server** `https://mcp.dice.com/mcp` tool `search_jobs` (no key required for public search). | None for public MCP | `page_number` / `jobs_per_page` | Be polite; bound pages | skills via keyword search, employment type, workplace, salary/hourly, employer type, easy apply, visa, apply URL | URL revalidation | MCP protocol/SSE shape changes | **Automated Dice MCP adapter**. |
| **CrunchBoard** | **Official RSS** `https://www.crunchboard.com/jobs.rss`. | None | Feed (latest window) | Low | title, company (in title), location, description, pubDate, URL | URL revalidation | Feed may be thin / empty at times | **Automated RSS adapter**. |

### Compliance notes

- Prefer official feeds/APIs (Dice MCP, CrunchBoard RSS, YC public HTML JSON).
- Import fallbacks require the operator to supply data they are entitled to use
  (e.g. personal exports, partner feeds, manually curated lists).
- Never scrape behind login walls; never ingest Glassdoor review bodies.
- One source failure must not abort the orchestrator (existing behavior).

## Architecture

### Source capability registry

New domain module `ingestion/domain/source_capabilities.py`:

```python
class SourceCapabilities(BaseModel):
    source: str
    display_name: str
    source_type: SourceType  # api | rss | scraper | manual
    integration: str         # official_api | official_rss | public_structured | import_fallback
    enabled_by_default: bool
    requires_credentials: bool
    supports_keyword_search: bool
    supports_location_search: bool
    supports_remote_filter: bool
    supports_pagination: bool
    provides_salary: bool
    provides_equity: bool
    provides_company_metadata: bool
    provides_technology_tags: bool
    snapshot_source: bool
    reliable_closure_detection: bool  # snapshot disappearance OR durable expiry
    closure_strategy: Literal["snapshot", "url_probe", "expiry", "none"]
    limitations: str = ""
```

Registry covers **all** board sources (existing + new). Exposed via
`GET /ingestion/sources` (capabilities + enabled flag) and used by the frontend
instead of a hard-coded incomplete list.

### Normalized metadata extensions

Extend `NormalizedJob` + ORM (Alembic migration):

| Field | Type | Notes |
|---|---|---|
| `employment_type` | `str \| None` | full_time / part_time / contract / … when explicit |
| `equity_range` | `str \| None` | display string when explicit |
| `source_metadata` | `dict` | platform-specific structured extras; missing ≠ invented |

`salary_range` remains the human display string. Structured salary pieces
(`salary_min`, `salary_max`, `salary_currency`, `salary_period`) live inside
`source_metadata` when a source provides them explicitly — avoids inventing
columns every source leaves blank while still preserving structure.

`source_metadata` may also hold: `yc_batch`, `company_stage`, `team_size`,
`funding`, `easy_apply`, `employer_type`, `contract_duration`, `company_rating`,
`company_size`, `industry`, `headquarters`, `also_found_on`, `source_urls`.

Do **not** invent missing values; leave fields unset/`None`.

### Adapters (per platform)

| Source key | Adapter | Type | Closure |
|---|---|---|---|
| `dice` | `DiceMcpAdapter` | API (MCP JSON-RPC) | url_probe |
| `crunchboard` | `CrunchBoardAdapter` | RSS | url_probe |
| `yc_jobs` | `YCJobsAdapter` | scraper (public structured HTML JSON) | url_probe |
| `indeed` | `IndeedImportAdapter` | manual | none / url_probe if URL present |
| `wellfound` | `WellfoundImportAdapter` | manual | none / url_probe if URL present |
| `glassdoor` | `GlassdoorImportAdapter` | manual | none / url_probe if URL present |
| `monster` | `MonsterImportAdapter` | manual | none / url_probe if URL present |

Shared helpers (only when ≥2 adapters benefit):

- `adapters/_jsonl_import.py` — path-safe JSONL/CSV reader under import dir
- `domain/normalizers/_import_fields.py` — shared remote/salary/equity field mapping
- `adapters/_mcp_client.py` — minimal JSON-RPC + SSE `data:` parser for Dice

### Source health

In-process `SourceHealthTracker` on the orchestrator (same process-memory model as
metrics / cooldown — documented single-worker constraint):

- last_attempt_at, last_success_at, duration_ms
- pages_fetched, jobs_discovered, jobs_created, jobs_updated
- jobs_deduplicated, jobs_rejected_malformed
- rate_limited_count, parse_failures
- status: `healthy` \| `degraded` \| `failing` \| `disabled` \| `not_configured`
- last_error

Exposed at `GET /ingestion/sources/health`. OTel metrics continue to record
`jobs_fetched_total` / `source_fetch_duration_ms`.

### Cross-source dedup / provenance

Keep persistence identity per source. At list-time consolidation:

1. Existing company+title canonical key.
2. Prefer ATS_FORM → non-empty apply_url → **source tier** (portals/greenhouse…
   > company boards like yc_jobs/wellfound > aggregators indeed/monster/glassdoor/
   dice/crunchboard/linkedin) → newer posted_date → richer description/skills.
3. Attach provenance onto the representative’s `source_metadata`:
   `also_found_on: [{source, url, posted_date, job_id}, …]`.

### Configuration

All knobs via `JobSourcesSettings` / `IngestionSettings` + `.env.example`:

- Enablement via `ENABLED_JOB_SOURCES` (dice, crunchboard, yc_jobs opt-in or
  default; import sources listed but idle without files).
- Per-source base URLs, page/result limits, remote-only, search keywords,
  locations, role lists (YC), MCP endpoint (Dice), import filenames.

### Frontend

- Load board sources from `GET /ingestion/sources` (fallback to static list).
- Source badges for new sources; capability tooltips / disabled warnings.
- Optional health strip on Discover when health endpoint returns failing sources.
- Display equity_range, employment_type, and selected `source_metadata` on job
  detail / cards when present.
- Preserve Angular standalone + signals patterns.

### Testing

- Unit tests with FakeHttp / fixture JSON for every adapter + normalizer.
- Import adapters: missing file → empty; malformed rows rejected; stable IDs.
- Dice MCP: parse SSE `data:` payloads; pagination bounds; HTTP errors.
- YC: parse Inertia fixtures; role fan-out; company enrichment optional.
- CrunchBoard: RSS fixture including company/location-from-title parsing.
- Registry registration + config enable/disable.
- Dedup provenance + source-tier precedence.
- Frontend: badge rendering, source filter options, metadata display.
- Optional `@pytest.mark.live_sources` smoke tests skipped by default.

### Documentation

- README source list update.
- This spec + plan.
- Ingestion sources section: capabilities, config, limitations, troubleshooting,
  how to add another source, optional live tests.

## Rollout / failure handling

1. Land adapters behind config; enable `dice`, `crunchboard`, `yc_jobs` by default
   (no credentials). Import sources available when filenames configured / files present.
2. Orchestrator already isolates per-source exceptions; health tracker records them.
3. Incomplete fetches never trigger snapshot closure (none of the new sources are
   snapshot sources).
4. If Dice MCP or YC HTML shape changes, source status → failing; others continue.

# Company intel on the company detail page — design

**Date:** 2026-07-05
**Status:** Specced

## Problem

The company detail page (`/dashboard/company/:name`) shows a company's open jobs
and a client-side summary header — but nothing *about the company itself*. There
is no industry, size, HQ, website, logo, or qualitative research on the page. The
data to do better already exists in the `research` module (LLM company research:
funding stage, tech stack, culture, growth, pros/cons, red flags), currently
surfaced only on the Applications page — never on the company page it most
naturally belongs to.

## Goal

Give the company detail page a **company intel** panel:

1. **Firmographics** — industry, company size, headquarters, website, logo.
2. **Qualitative research** — the existing LLM research fields.
3. Populate it automatically on first visit, cache it, and offer a manual
   refresh.

## Scope

In scope: extending the `research` module with firmographics + a layered
firmographics source (external provider → LLM fallback), logo derivation,
auto-on-first-visit generation, and the frontend intel panel.

Out of scope: company-name normalization/aliasing (still exact, case-insensitive
match as in the company-pages spec), following/persistence changes, backfilling
research for all companies.

## Architecture

Extend the existing hexagonal `research` module. No new bounded context.

```
Company page load
  → research.service GET /research/{name}
      → CompanyResearchService.get_or_create(name)
          cached? → return
          else    → FirmographicsPort (external → LLM fallback)
                    + LLM qualitative research (existing)
                    → persist (company_research row)
      → API layer derives logo_url from website domain
  → CompanyIntelComponent renders panel
```

### Backend

**1. Data model + migration.**

Add four nullable columns to `CompanyResearch` (domain model) and
`CompanyResearchOrm`:

- `industry: str | None`
- `company_size: str | None`
- `headquarters: str | None`
- `website: str | None`

Alembic migration adds the columns (all nullable, no backfill). ORM already
registered in `infrastructure/registry.py`. Logo is **not** stored — derived at
read time from `website`.

**2. Firmographics source — layered, ports/adapters.**

New `FirmographicsPort` (Protocol) in `research/ports/` returning a small
`Firmographics` value object (`industry`, `company_size`, `headquarters`,
`website`), or `None` when unavailable.

- `ExternalFirmographicsAdapter` (`research/infrastructure/`) — calls a
  configurable enrichment provider. Reads base URL + API key from a config
  group. Returns `None` when unconfigured (local mode) or on any error/timeout.
  This is the preferred source when configured.
- `LlmFirmographicsAdapter` — fallback. The existing research LLM call already
  returns JSON; extend its prompt + parsing to also emit `industry`,
  `company_size`, `headquarters`, `website`. When the external adapter returns a
  value it wins; otherwise the LLM values are used.

The service composes them: try external first; for any field the external source
didn't supply, fall back to the LLM values. Firmographics and qualitative
research are produced in the same generation pass so first-visit does one round
of work.

**3. Logo derivation.**

At the API layer, derive `logo_url` from the `website` domain via a configurable
logo-service base URL (`LOGO_SERVICE_URL`, e.g. a favicon/logo CDN that takes a
domain). If `website` is missing, `logo_url` is `None`. No fetching server-side —
the frontend loads the URL and falls back to a monogram on error. Domain
extraction is a pure helper (strip scheme/path, keep host).

**4. Trigger behavior.**

`GET /research/{company}` becomes get-or-create:

- Cached row present → return it (fast path for repeat visits).
- Absent → generate once (firmographics + qualitative), persist, return.
- Local mode with no LLM and no external provider → the existing graceful
  "not configured" fallback record (fields set to a not-configured sentinel),
  persisted or returned as today. No crash.

`POST /research/refresh` (already exists) backs the manual **Refresh** button and
re-runs generation, overwriting the cached row.

**5. API schema.**

`CompanyResearchResponse` gains `industry`, `company_size`, `headquarters`,
`website`, `logo_url` (all optional). Existing fields unchanged.

### Frontend

`frontend/src/app/`:

1. **`core/services/research.service.ts`** — extend the response model with the
   new optional fields; ensure a `GET /research/{name}` method and a refresh
   method exist.
2. **`pages/company/components/company-intel/`** — new presentational component
   (OnPush, signals via inputs):
   - Logo (rounded), with a **monogram fallback** (company initials) when there
     is no `logo_url` or the image errors.
   - Firmographics row: industry · company size · HQ · website (external link).
   - Research sections: funding stage, tech stack, culture summary, growth
     trajectory, pros / cons, red flags (only render sections that have content;
     hide not-configured sentinels).
   - States: loading, "not configured" (local/no-LLM), and a **Refresh** button
     (calls the refresh endpoint, shows in-progress).
3. **`pages/company/company.component.ts`** — on init, in addition to the job
   `forkJoin`, call the research service for `:name`. Research loads independently
   of jobs (its own loading/error signals) so a slow/absent research call never
   blocks the job list. Render `<app-company-intel>` above the jobs table.

## Config additions

Added to the appropriate `config/groups/` group + `.env.example` (with comments),
never hardcoded:

- `FIRMOGRAPHICS_PROVIDER_URL` — external enrichment base URL (blank ⇒ adapter
  disabled).
- `FIRMOGRAPHICS_API_KEY` — provider key (blank ⇒ adapter disabled).
- `LOGO_SERVICE_URL` — logo/favicon service base URL (domain-templated).

All blank by default so local mode degrades to LLM + monogram with no config.

## Testing

- **Firmographics service composition:** external wins when present; LLM fills
  gaps; both absent ⇒ not-configured. (unit)
- **Logo derivation:** domain extraction from various website strings; `None`
  when no website. (unit)
- **`get_or_create`:** cached returns without generating; absent generates once
  and persists; refresh overwrites. (unit with fake repo/LLM/provider)
- **Endpoint:** `GET /research/{name}` returns the new fields incl. `logo_url`;
  local-mode no-LLM returns graceful state (not 500). (integration, in-memory)
- **Frontend:** `CompanyIntelComponent` renders firmographics + research from a
  mocked service; monogram fallback on missing logo; refresh triggers the
  service; not-configured state. (Vitest)

## Decisions & limitations

- **Same-company identity is still the exact, case-insensitive name string** —
  matches the company-pages spec; no aliasing.
- **Firmographics accuracy depends on the source.** LLM firmographics are
  best-effort and may be stale/approximate; the external provider (when
  configured) is preferred precisely for this reason.
- **First-visit latency:** generating on first visit adds a one-time delay for
  that company; subsequent visits are cached and fast. Research loads
  independently so the jobs table renders immediately regardless.
- **Logo is never persisted** — it's a pure function of `website` + config, so it
  updates for free if the logo service or website changes.

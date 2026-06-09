# Portfolio Integration — Design

**Date:** 2026-06-09
**Status:** Approved
**Owner module:** new `portfolio` bounded context (backend), `pages/portfolio` + touchpoints (frontend)

## Problem

`portfolio_url` is a stored profile field that nothing consumes. The candidate's real,
up-to-date proof of work — their portfolio site — is invisible to matching, scoring, deep
analysis, and every generated artifact (cover letters, outreach). There is also no signal
about whether recruiters ever visit the portfolio after an application goes out.

Reference portfolio: `https://stevsant.vercel.app` (Angular 21 SPA + Supabase). Verified
facts that shape this design:

- The site is client-rendered: plain HTTP fetch returns an empty shell. Scraping is not viable.
- Supabase PostgREST is the real API. `project`, `project_translation`, `skill`,
  `skill_usages`, `language` have **public-read RLS** (`USING (true)`) — readable with the
  anon key, no portfolio changes required.
- Schema (from the portfolio repo `supabase/tables/`):
  - `project(id, code, url, demo_url, created_at, parent_project_id, is_archived, is_pinned, position)`
  - `project_translation(project_id, language_id, title, description)` — EN/ES via `language(id, code)`
  - `skill_usages(skill_id, source_id, source_type, level, …)` — polymorphic link; `source_type='project'` rows carry each project's tech stack
- The portfolio's analytics tracker already records `?ref=` / `?utm_source=` /
  `/from/:source` into `visitor_session.referrer_source`, plus `page_view` and
  `cv_download` tables. Anon role can INSERT/UPDATE but not SELECT `visitor_session` —
  readback needs a separate key.

## Goals

1. **Enrich the matching profile** with portfolio projects so semantic pre-ranking, quick
   scoring, and deep analysis know about real projects (not just the CV).
2. **Use projects in applications**: cover letters and outreach cite the 1–2 most relevant
   projects per job and link the portfolio with a per-application tracked ref.
3. **Track engagement**: surface "recruiter visited your portfolio" per application.
4. Stay **loosely coupled**: the portfolio source sits behind a port; other people's
   portfolios (different stacks) integrate by writing a new adapter, not by changing the
   domain.

## Non-goals (YAGNI)

- No headless-browser scraping of arbitrary portfolios.
- No multi-portfolio-per-user; one configured source per instance.
- No write-back to the portfolio.
- No self-scheduled sync (same policy as ingestion revalidation: manual trigger now,
  external cron later if wanted).

## Architecture

New bounded context `src/hiresense/portfolio/` with the standard layout
(`api → domain ← infrastructure`, ports as Protocols, wiring only in `bootstrap/`).

### Domain

- `PortfolioProject` (Pydantic): `id` (HireSense uuid), `source` (adapter name, e.g.
  `"supabase"`, `"github"`), `source_key` (the source's stable id — portfolio `code`,
  GitHub repo full name), `url`, `demo_url`, `pinned`, `position`, `tech: list[str]`,
  `translations: dict[str, ProjectText]` where `ProjectText = {title, description}` keyed
  by language code (`en`/`es`).
- `PortfolioSyncService`: `sync() -> SyncResult` — iterates the configured source
  adapters (mirroring how ingestion iterates `enabled_job_sources`), calls each
  `PortfolioSourcePort.fetch_projects()`, normalizes, and **replaces** that source's
  slice of the stored snapshot in one transaction (no partial state). A failing source
  leaves its previous slice intact and is reported in `SyncResult.errors`; other sources
  still sync. Archived projects are excluded at fetch time.
- `RelevantProjectSelector` (pure): `select(job_skills, job_text, projects, top_n) ->
  list[PortfolioProject]` — ranks by overlap between job skills/description and project
  `tech` + title tokens. Deterministic, no LLM. Pinned projects win ties.
- `portfolio_profile_text(projects, language, char_cap) -> str` (pure): compact
  "Portfolio projects" block (title — tech — one-line description) used for profile
  enrichment; capped to `portfolio_profile_char_cap`.

### Ports

- `PortfolioSourcePort` (Protocol): `async fetch_projects() -> list[PortfolioProject]`.
- `PortfolioEngagementPort` (Protocol, Phase 3):
  `async fetch_visits(ref_prefix) -> list[PortfolioVisit]` where `PortfolioVisit =
  {ref, first_seen, last_seen, page_views, cv_downloads, country, organization}`.

### Adapters (infrastructure)

- `SupabasePortfolioAdapter(http_client, base_url, anon_key)` — PostgREST reads:
  - `GET {base}/rest/v1/language?select=id,code`
  - `GET {base}/rest/v1/project?select=id,code,url,demo_url,is_pinned,position,project_translation(language_id,title,description)&is_archived=eq.false`
  - `GET {base}/rest/v1/skill_usages?select=source_id,skill(code)&source_type=eq.project&is_archived=eq.false`
  - Headers: `apikey: <anon_key>`, `Authorization: Bearer <anon_key>`.
  - Uses the shared retrying HTTP client (`infra.http_client`) and `http_timeout`.
- `SupabaseEngagementAdapter(http_client, base_url, read_key)` (Phase 3) — queries
  `visitor_session?referrer_source=like.{prefix}-*` joined with `page_view` counts.
  `read_key` is a **separate** config value (anon cannot SELECT `visitor_session`);
  feature is disabled when unset.

### Persistence

- `PortfolioProjectOrm` → table `portfolio_projects` (snapshot of last sync; columns
  mirror the domain model, translations + tech as JSON). Registered in
  `infrastructure/registry.py`; Alembic migration via autogenerate.
- `PortfolioProjectsRepository` (sync sessions, same pattern as other repos; called via
  `asyncio.to_thread` from async paths per the audit convention).

### API

`/portfolio` router — router-level `require_auth`, expensive endpoints rate-limited:

- `POST /portfolio/sync` (rate-limited): fetch + replace snapshot → `{projects: N, synced_at}`.
  502 with detail when the source is unreachable; snapshot untouched on failure.
- `GET /portfolio/projects`: list the stored snapshot (+ `last_synced_at`).

### Configuration (config.py + .env + .env.example)

```
PORTFOLIO_SOURCES=supabase                # comma-separated adapter list (like ENABLED_JOB_SOURCES); empty disables the module
PORTFOLIO_SUPABASE_URL=                   # Supabase project URL (https://xyz.supabase.co)
PORTFOLIO_SUPABASE_ANON_KEY=              # public anon key (read-only by RLS)
PORTFOLIO_PUBLIC_URL=https://stevsant.vercel.app   # link target in artifacts
PORTFOLIO_REF_PREFIX=hiresense            # tracked-link slug prefix
PORTFOLIO_PROFILE_CHAR_CAP=1200           # enrichment text cap
PORTFOLIO_RELEVANT_PROJECTS_TOP_N=2
PORTFOLIO_ANALYTICS_READ_KEY=             # Phase 3; empty disables engagement readback
# Phase 1.5 (github adapter):
# PORTFOLIO_GITHUB_USERNAME=              # public repos of this user
# PORTFOLIO_GITHUB_TOKEN=                 # optional PAT (rate limits / private repos)
```

When `PORTFOLIO_SOURCES` is empty the provider is `None` and every consumer degrades to
today's behavior (the module is fully optional — key to "other people" reuse). Each
adapter reads only its own config keys; enabling a source without its keys is a startup
configuration error.

## Phase 1 — Sync + profile enrichment

- Bounded context, Supabase adapter, repository + migration, sync/list endpoints.
- Enrichment composition (no cross-domain imports): `bootstrap` passes an optional
  `portfolio_projects_read` callable into the **ingestion** build; `_gather_profile`
  (ingestion api) and the matching profile assembly append `portfolio_profile_text(...)`
  to `candidate_summary` and union project `tech` into `candidate_skills`.
- Frontend: "Portfolio" card on the profile page — synced project list, "Sync now"
  button, last-synced timestamp, link to the public site.

## Phase 2 — Applications

- `RelevantProjectSelector` output injected into cover-letter and outreach prompts as a
  "Relevant portfolio projects" section (language-aware: pick the translation matching
  `cv_language`, fall back to EN).
- Tracked link appended to generated artifacts:
  `{PORTFOLIO_PUBLIC_URL}/?ref={PORTFOLIO_REF_PREFIX}-{application_id}`.
  The portfolio records this today without changes.
- Frontend: application detail shows which projects were cited.

## Phase 3 — Engagement readback

- `SupabaseEngagementAdapter` + `GET /portfolio/engagement` mapping visits to
  applications by ref slug.
- Tracking/application detail: "Portfolio visited — N page views, last seen …" chip.
- Analytics dashboard: small engagement card (visits by application, CV downloads).
- Entirely absent from the UI when `PORTFOLIO_ANALYTICS_READ_KEY` is unset.

## Error handling

- Sync: any fetch/parse failure aborts before the transaction — previous snapshot stays;
  endpoint returns 502 with an actionable detail message.
- Enrichment/generation: missing or empty snapshot → consumers behave exactly as today.
- Engagement: fetch failure logs a warning and renders "no data".

## Testing

- Unit: adapter normalization against canned PostgREST JSON; selector ranking
  (overlap, pinned tie-break, top_n); profile-text capping; ref-slug formatting.
- Integration: sync + list endpoints with a fake `PortfolioSourcePort`
  (`dependency_overrides` + `require_auth` override per existing convention); enrichment
  visible in `_gather_profile` output; everything green without network/Supabase.
- No live Supabase in CI. Manual smoke against the real portfolio documented in the plan.

## Roadmap: additional account sources (approved direction, own specs later)

The port/adapter split exists precisely so other "proof of work / account" sources can
feed the same pipeline. Agreed follow-ups, in priority order:

1. **Phase 1.5 — GitHub adapter** (second `PortfolioSourcePort` implementation; validates
   the port). Public REST API: repos → `PortfolioProject` (name/description/topics +
   languages as `tech`; stars/pinned-equivalent via `position`). Config:
   `PORTFOLIO_GITHUB_USERNAME`, optional `PORTFOLIO_GITHUB_TOKEN`. Small enough to ride
   the Phase 1 architecture with no design changes.
2. **LinkedIn data-export import** (own spec; different shape — NOT a portfolio source).
   Research findings (2026-06-09): there is no usable personal API — "Sign in with
   LinkedIn" exposes only name/email/photo, the Member Data Portability API is EU/EEA-only
   (DMA), and logged-in scraping violates ToS. The viable path is LinkedIn's data-export
   ZIP (Settings → "Get a copy of your data"): import `Positions.csv`/`Skills.csv` into
   the profile, and `Connections.csv` into a new contacts store powering
   "you know someone at this company" badges on job listings and outreach suggestions.
   Refresh = re-upload a new export.
3. **GetOnBoard account sync** (research task first). Their API docs mention
   authentication to "manage jobs, applications and recruitment processes", but it is
   unclear whether that is job-seeker-side or employer-side. If a personal authenticated
   API exists, auto-sync application status into the tracking module; otherwise drop.

## Rollout

Three phases = three spec'd plans / PRs. Phase 1 first; Phases 2–3 each get a short plan
referencing this spec. Roadmap items 1–3 above are separate initiatives: item 1 is a
small plan against this spec; items 2–3 get their own specs (and item 3 starts as a
research note, not code).

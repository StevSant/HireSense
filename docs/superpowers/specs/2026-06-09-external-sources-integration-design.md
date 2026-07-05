# External Sources Integration — Design

**Date:** 2026-06-09
**Status:** Approved
**Scope:** four external sources, one shared philosophy — portfolio (Supabase), GitHub,
LinkedIn (data export), GetOnBoard (account). Backend: new `portfolio` and `network`
bounded contexts + touchpoints in `profile`, `ingestion`, `outreach`, `tracking`.

## Problem

HireSense knows the candidate only through the uploaded CV. Everything else the
candidate has built lives in accounts HireSense never reads:

- The **portfolio site** (real projects, tech stacks, EN/ES descriptions) is invisible to
  matching, scoring, deep analysis, and generated artifacts. `portfolio_url` is stored
  but never consumed.
- **GitHub** (repos, languages, topics) — same invisibility; `github_url` is stored but
  never consumed.
- **LinkedIn** holds the authoritative work history, skills, and — most valuably — the
  **connections list**: knowing someone at a hiring company changes how you apply, yet
  HireSense can't surface it.
- **GetOnBoard** is where applications actually get submitted (for LATAM roles), but
  their status never flows back into HireSense tracking.

There is also no feedback loop: no signal whether recruiters ever open the portfolio
after an application goes out.

## Goals

1. **Enrich the matching profile** with real proof-of-work (portfolio + GitHub projects)
   so semantic pre-ranking, quick scoring, and deep analysis see actual projects.
2. **Use projects in applications**: cover letters and outreach cite the 1–2 most
   relevant projects per job, linking the portfolio with a per-application tracked ref.
3. **Import LinkedIn**: positions/skills merge into the profile; connections power
   "you know someone at this company" signals on job listings and outreach.
4. **Sync GetOnBoard applications** into tracking (feasibility-gated; research first).
5. **Track engagement**: surface "recruiter visited your portfolio" per application.
6. Stay **loosely coupled**: every source sits behind a port; a different stack
   integrates by writing an adapter, never by changing domain code. Every source is
   optional — unconfigured sources leave behavior exactly as today.

## Non-goals (YAGNI)

- No headless-browser scraping of any site (the portfolio is an SPA shell; LinkedIn
  scraping violates ToS and risks the account).
- No live LinkedIn API integration — none usable exists (see Part B research notes).
- No multi-account-per-source; one configured account per instance.
- No write-back to any external source.
- No self-scheduled syncs (manual trigger now; external cron later, same policy as
  ingestion revalidation).

## Source overview

| Source | What we read | How | Feeds |
|---|---|---|---|
| Portfolio (Supabase) | projects + tech + EN/ES texts | PostgREST, anon key (public RLS — verified) | profile enrichment, artifact citation, engagement |
| GitHub | repos, languages, topics, descriptions | public REST API (+ optional PAT) | profile enrichment, artifact citation |
| LinkedIn | positions, skills, education, **connections** | data-export ZIP upload (only ToS-clean path) | profile merge, network badges, outreach targeting |
| GetOnBoard | own applications + status | authenticated API — **feasibility unproven** | tracking auto-sync |
| Portfolio analytics | visitor sessions, page views, CV downloads | PostgREST with separate read key | per-application engagement |

---

## Part A — Proof-of-work sources (portfolio + GitHub)

New bounded context `src/hiresense/portfolio/` with the standard layout
(`api → domain ← infrastructure`, ports as Protocols, wiring only in `bootstrap/`).

### Domain

- `PortfolioProject` (Pydantic): `id` (HireSense uuid), `source` (adapter name:
  `"supabase"`, `"github"`), `source_key` (stable id — portfolio `code` / repo full
  name), `url`, `demo_url`, `pinned`, `position`, `tech: list[str]`,
  `translations: dict[str, ProjectText]` (`ProjectText = {title, description}`, keyed by
  `en`/`es`; GitHub yields `en` only).
- `PortfolioSyncService.sync() -> SyncResult` — iterates the configured source adapters
  (mirroring how ingestion iterates `enabled_job_sources`); each source's slice of the
  snapshot is **replaced in one transaction**. A failing source leaves its previous
  slice intact and lands in `SyncResult.errors`; other sources still sync.
- `RelevantProjectSelector` (pure): ranks projects against a job by overlap between job
  skills/description and project `tech` + title tokens. Deterministic, no LLM; pinned
  projects win ties.
- `portfolio_profile_text(projects, language, char_cap)` (pure): compact
  "Portfolio projects" block for profile enrichment, capped by config.

### Ports

- `PortfolioSourcePort`: `async fetch_projects() -> list[PortfolioProject]`.
- `PortfolioEngagementPort` (Part D): `async fetch_visits(ref_prefix) ->
  list[PortfolioVisit]` (`{ref, first_seen, last_seen, page_views, cv_downloads,
  country, organization}`).

### Adapters

**`SupabasePortfolioAdapter(http_client, base_url, anon_key)`** — verified against the
portfolio repo (`StevSant26`, Angular 21 + Supabase; tables have public-read RLS):

- `GET {base}/rest/v1/language?select=id,code`
- `GET {base}/rest/v1/project?select=id,code,url,demo_url,is_pinned,position,project_translation(language_id,title,description)&is_archived=eq.false`
- `GET {base}/rest/v1/skill_usages?select=source_id,skill(code)&source_type=eq.project&is_archived=eq.false`
- Headers `apikey` + `Authorization: Bearer` with the anon key; shared retrying HTTP
  client; `http_timeout`.

**`GitHubPortfolioAdapter(http_client, username, token?)`**:

- `GET https://api.github.com/users/{username}/repos?per_page=100&sort=pushed&type=owner`
  → name, description, html_url, homepage (→ `demo_url`), topics, stargazers_count;
  forks and archived repos excluded.
- `GET /repos/{owner}/{repo}/languages` for `tech` (top languages by bytes), merged with
  `topics`.
- Optional `token` raises rate limits (60 → 5000 req/h) and includes private repos;
  without it, public repos only. Stars + recent push order maps to `position`.

### Persistence & API

- `PortfolioProjectOrm` → `portfolio_projects` table (translations + tech as JSON,
  `source` column); registered in `infrastructure/registry.py`; Alembic autogenerate.
- `/portfolio` router (router-level `require_auth`; sync rate-limited):
  - `POST /portfolio/sync` → `{counts_by_source, errors, synced_at}`; 502 only when ALL
    sources fail.
  - `GET /portfolio/projects` → snapshot + `last_synced_at`.

### Profile enrichment (consumes Part A)

Composition in `bootstrap` (no cross-domain imports): an optional
`portfolio_projects_read` callable is passed into the ingestion build; `_gather_profile`
(ingestion api) and the matching profile assembly append `portfolio_profile_text(...)`
to `candidate_summary` and union project `tech` into `candidate_skills`.

---

## Part B — LinkedIn data-export import

**Research findings (2026-06-09), recorded so nobody re-litigates this:** there is no
usable personal LinkedIn API. "Sign in with LinkedIn" (OpenID Connect) exposes only
name/email/photo. The Member Data Portability API exists but is EU/EEA-only (DMA).
Logged-in scraping violates ToS and risks the account; third-party scraping APIs are
paid, ToS-gray, and the largest was litigated into shutdown. **The data-export ZIP is
the only clean path** (Settings → "Get a copy of your data"; regenerable on demand;
refresh = re-upload a new export).

### What the export contains (CSV, stable LinkedIn format)

- `Positions.csv`: Company Name, Title, Description, Location, Started On, Finished On
- `Skills.csv`: Name
- `Education.csv`, `Profile.csv`
- `Connections.csv`: First Name, Last Name, URL, Email Address, Company, Position,
  Connected On — **the high-value file**

### Design

Two consumers, two homes:

1. **Profile merge (`profile` module):** `POST /profile/import-linkedin` accepts the ZIP
   (or individual CSVs), parses Positions/Skills/Education, and merges into the current
   profile: skills union (deduped, case-insensitive), positions appended to a structured
   experience section of the profile text used by matching. The merge is additive and
   idempotent — re-upload replaces the previously imported LinkedIn slice (rows tagged
   by origin) and never touches CV-derived content. Upload validation follows the
   existing hardening pattern (ZIP magic `PK`, size caps, per-file extension checks).
2. **Network (`network` bounded context, new):**
   - Domain: `Contact` (`first_name`, `last_name`, `linkedin_url`, `email`, `company`,
     `position`, `connected_on`, `company_normalized`).
   - `company_normalized`: lowercase, strip legal suffixes (inc, llc, s.a., ltd, gmbh…)
     and punctuation — one pure function with tests, reused by the matcher.
   - Infrastructure: `ContactOrm` → `network_contacts` table + repository; Alembic
     migration; registered in `registry.py`.
   - API (router-level `require_auth`): `POST /network/import` (ZIP/CSV upload),
     `GET /network/contacts?company=`, `GET /network/match?company=<name>`.
   - **Job-list badge:** the ingestion list response gains `connections_count` per job
     (bootstrap passes an optional `network_lookup` callable; computed against the
     visible page only — a dict lookup on `company_normalized`, no LLM).
   - **Outreach targeting:** given a job/company, outreach offers matched contacts as
     suggested recipients ("warm intro") with their position.

**Privacy:** contacts are personal data. They stay in the local DB, are never included
in LLM prompts (badges and matching are deterministic), and all endpoints require auth.

---

## Part C — GetOnBoard account sync (research-gated)

GetOnBoard's API docs mention authentication to "manage jobs, applications and
recruitment processes" — but it is unclear whether that covers the **job-seeker** side
(my applications, their status) or only the employer side.

- **Step 1 — research, no code:** authenticate with the user's account token; enumerate
  user-scoped endpoints; record the outcome as a short note in
  `docs/superpowers/specs/`.
- **Step 2 — only if feasible:** `GetOnBoardAccountAdapter` in the `tracking` module —
  map their application records to tracking entries by job identity (jobs with
  `source=getonboard` already exist via ingestion) and translate their statuses onto the
  tracking status taxonomy. Manual `POST /tracking/sync-getonboard` trigger; same
  optional-config pattern (`GETONBOARD_API_TOKEN` empty → feature absent everywhere).
- **If not feasible:** drop the integration; manual status mirroring is what tracking
  already does.

---

## Part D — Portfolio engagement readback

The portfolio's analytics tracker already records `?ref=` / `?utm_source=` /
`/from/:source` into `visitor_session.referrer_source`, plus `page_view` and
`cv_download` rows (verified in the portfolio repo). Anon can INSERT/UPDATE but not
SELECT — readback needs a separate read key.

- Artifacts (Part A citation step) link
  `{PORTFOLIO_PUBLIC_URL}/?ref={PORTFOLIO_REF_PREFIX}-{application_id}` — recorded by
  the portfolio today with zero changes on its side.
- `SupabaseEngagementAdapter(http_client, base_url, read_key)` queries
  `visitor_session?referrer_source=like.{prefix}-*` plus `page_view` counts.
- `GET /portfolio/engagement` maps visits to applications by ref slug.
- UI: "Portfolio visited — N page views, last seen …" chip on application detail /
  tracking; small engagement card on the analytics dashboard.
- Entirely absent when `PORTFOLIO_ANALYTICS_READ_KEY` is unset.

---

## Configuration (config.py + .env + .env.example — every value, no hardcoding)

```
# --- Proof-of-work sources (Part A) ---
PORTFOLIO_SOURCES=supabase,github         # comma-separated adapter list; empty disables
PORTFOLIO_SUPABASE_URL=
PORTFOLIO_SUPABASE_ANON_KEY=
PORTFOLIO_GITHUB_USERNAME=
PORTFOLIO_GITHUB_TOKEN=                   # optional: rate limits / private repos
PORTFOLIO_PUBLIC_URL=https://your-portfolio.example.com
PORTFOLIO_REF_PREFIX=hiresense
PORTFOLIO_PROFILE_CHAR_CAP=1200
PORTFOLIO_RELEVANT_PROJECTS_TOP_N=2
# --- Engagement readback (Part D) ---
PORTFOLIO_ANALYTICS_READ_KEY=             # empty disables
# --- GetOnBoard account (Part C, only if research says feasible) ---
GETONBOARD_API_TOKEN=                     # empty disables
```

LinkedIn import needs no env config — it is an upload, not a live connection.

Each adapter reads only its own keys; enabling a source in `PORTFOLIO_SOURCES` without
its keys is a startup configuration error (same fail-loud philosophy as the placeholder
secret validators).

## Error handling

- Sync (Part A): per-source isolation — a failing source keeps its previous slice and is
  reported; 502 only if all sources fail.
- LinkedIn import (Part B): malformed/oversized files → 400 with detail; partial exports
  are fine (import whatever known files the ZIP contains, report counts per file).
- Enrichment / badges / citation: missing data → consumers behave exactly as today.
- Engagement and GetOnBoard: fetch failures log a warning and render "no data".

## Testing

- Unit: each adapter's normalization against canned JSON/CSV fixtures; selector ranking;
  company normalization; profile-text capping; ref-slug formatting; ZIP validation.
- Integration: sync/import/list endpoints with fake ports (`dependency_overrides` + the
  `require_auth` override convention); enrichment visible in `_gather_profile` output;
  badge counts on the jobs list. No network access in CI.
- Manual smoke per source documented in each phase's plan.

## Rollout — phases, each its own plan + PR

| Phase | Delivers | Depends on |
|---|---|---|
| 1 | `portfolio` context, Supabase adapter, sync/list endpoints, profile enrichment, profile-page card | — |
| 2 | GitHub adapter (second source; validates the port) | 1 |
| 3 | Artifact citation: relevant projects + tracked ref links in cover letters/outreach | 1 |
| 4 | `network` context: LinkedIn import (profile merge + contacts), job-list badges, outreach suggestions | — (parallel to 1) |
| 5 | Engagement readback (Part D) | 3 |
| 6 | GetOnBoard research note → adapter only if feasible | — |

Phase 1 is the first implementation plan. Phases 4 and 6 are independent of the
portfolio work and can be scheduled freely.

# Apply Assist — Phase 0: application-method classification (design)

**Date:** 2026-06-14
**Status:** in progress
**Module:** `ingestion`

## Problem

HireSense cannot tell *how* to apply to a job. The normalized job model
(`ingestion/domain/models.py`) stores a single `url` and treats every posting
as "just open the link." This conflates three very different things:

- a **redirect** to an aggregator landing page (Remotive, Adzuna `redirect_url`,
  LinkedIn guest pages) — apply happens somewhere downstream;
- a **direct ATS application form** (Greenhouse `absolute_url`, Lever
  `hostedUrl`, Ashby `jobUrl`, Workable, SmartRecruiters, Recruitee) — the URL
  *is* the apply form;
- jobs with **no URL** at all.

Every downstream "apply assist" feature (an "applies directly" badge, and
later the prefill + one-click handoff that autofills ATS forms) needs this
distinction. It does not exist today, so Phase 0 adds it. This is the
prerequisite that unblocks the rest of the Apply Assist roadmap; see the audit
in the conversation of 2026-06-14.

## Approach

Add three fields to `NormalizedJob` and the `ingested_jobs` table, derived once
at ingestion by a single pure classifier:

| field | type | meaning |
|---|---|---|
| `application_method` | str (`ApplicationMethod`) | `ats_form` \| `redirect` \| `unknown` |
| `ats_type` | str \| None (`AtsPlatform`) | detected ATS when known: `greenhouse`/`lever`/`ashby`/`workable`/`smartrecruiters`/`recruitee` |
| `apply_url` | str \| None | a URL we are confident leads to an application form. Set = `url` for `ats_form`; `None` otherwise (reserved for later redirect-resolution work). |

### Classification rule (`classify_application(url, *, platform=None)`)

1. If `platform` (from `portals.yml`, authoritative for the *portals* bucket)
   matches a known ATS → `ats_form`, `ats_type = platform`, `apply_url = url`.
2. Else sniff the URL host (covers the *boards* bucket, where aggregators
   frequently link straight to an ATS): host ends with `greenhouse.io`,
   `lever.co`, `ashbyhq.com`, `workable.com`, `smartrecruiters.com`,
   `recruitee.com` → `ats_form` + matched `ats_type` + `apply_url = url`.
3. Else if there is a URL → `redirect`, `ats_type = None`, `apply_url = None`.
4. Else → `unknown`.

The classifier is a pure domain function (no I/O), called at the two existing
`NormalizedJob` construction sites — `IngestionOrchestrator` (boards,
`services.py`) and `PortalScanner` (portals, `portal_scanner.py`). No normalizer
changes are needed: classification is derived from the `url` the normalizers
already produce, plus the portal `platform`.

### Persistence

Three nullable columns on `ingested_jobs` with safe server defaults so existing
rows backfill harmlessly: `apply_url` (NULL), `application_method`
(`'unknown'`), `ats_type` (NULL). New rows are classified on insert. As with
`url`, these are set once at insert and not rewritten on content updates
(`_apply_to_row` already leaves `url` untouched). Alembic migration adds the
columns; the ORM class is already in `infrastructure/registry.py`.

`content_hash` is unchanged — these fields are derived from `url` (which is part
of identity, not content) and must not affect change detection.

## Out of scope (later phases)

- Resolving aggregator redirects to the final ATS URL (would populate
  `apply_url` for `redirect` jobs).
- The structured "Apply Profile" answer bank (Phase 1).
- The browser-extension autofill + handoff (Phase 2).
- Promoting ATS portals into the default source set / the "applies directly"
  UI badge (small follow-ups once the data exists).

## Testing

- `test_application_classifier.py`: each ATS host (incl. subdomains like
  `job-boards.greenhouse.io`, `company.recruitee.com`), portal-platform
  override, aggregator → redirect, empty URL → unknown.
- Repository round-trip: the three fields survive `_to_orm` / `_to_domain`.
- Full suite stays green and DB-free (SQLite).

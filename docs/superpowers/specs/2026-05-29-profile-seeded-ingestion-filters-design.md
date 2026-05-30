# Profile-seeded ingestion filters — Design

**Date:** 2026-05-29
**Status:** Approved (pending spec review)

## Problem

The ingestion page (`/dashboard/ingestion`) presents manual filter controls for
seniority and max-years-experience. These start empty, so the user fills them in
by hand every visit — even though the system already knows the candidate's
profile. The *scoring* (the `MATCH %` column) is fully profile-driven, but the
*filters* are not, creating a perceived gap: "ingestion should be based on my
profile."

There is already a built primitive, `infer_candidate_level()` in
`ingestion/domain/candidate_level.py`, that derives a seniority level from CV
text — but it is currently dead code, wired to nothing.

## Goal

On first load of the ingestion page, pre-select the seniority band and max-years
cap that match the candidate's CV, while keeping every control manually
overridable. No profile-model changes — pure inference from existing CV text.

## Decisions

| Decision | Choice |
|---|---|
| Behavior | Seed filter defaults from profile, keep manual override |
| Source of truth | Infer from CV text (reuse existing `infer_candidate_level`); no new profile fields |
| Seniority breadth | Inferred level ±1 (a band, e.g. Mid → Junior + Mid + Senior) |
| Max-years seeding | Seed with a buffer: CV years + buffer (default 2) |

## Architecture

Three small pieces.

### 1. Backend — inference endpoint

New route `GET /ingestion/profile-defaults` returning:

```json
{ "seniority": ["junior", "mid", "senior"], "max_years_experience": 5 }
```

Logic lives in a new single-purpose module `ingestion/domain/profile_filter_defaults.py`
(one function, per the one-definition-per-file convention), re-exported from the
`ingestion.domain` package `__init__.py`.

- Reuse the existing `_gather_profile` helper to obtain the CV summary blob.
- `infer_candidate_level(summary)` → a `SeniorityLevel`.
- **Band ±1:** map the level onto the ordered list
  `[INTERN, JUNIOR, MID, SENIOR, LEAD]`, return `[level-1, level, level+1]`
  clamped to the ends. If the inferred level is `UNKNOWN`, return `[]`
  (meaning: seed nothing, show all levels).
- **Years:** `extract_min_years(summary)`; if a value is found, return
  `years + buffer`; otherwise return `None`.
- **Buffer is configurable**, never hardcoded: add
  `ingestion_seniority_years_buffer` to `config.py` (default `2`) and document it
  in `.env.example` with a placeholder + comment.

The endpoint depends on `ProfileService` (as the existing list endpoint does) and
is graceful when no profile exists: inference returns `UNKNOWN` / `None`, so the
response is `{ "seniority": [], "max_years_experience": null }`.

### 2. Frontend — service method

Add `getProfileFilterDefaults()` to `core/services/ingestion.service.ts`, calling
the new endpoint and returning `{ seniority: SeniorityLevel[]; max_years_experience: number | null }`.

### 3. Frontend — seed-once on load

In `JobFiltersComponent.ngOnInit`, alongside the existing location/strict
`localStorage` seeding:

- If a `hiresense.filters_seeded` marker is **absent** in `localStorage`, fetch
  the defaults, emit `seniority` + `max_years_experience` into the filter state,
  then set the marker.
- If the marker is **present**, do nothing — the user's manual choices persist
  and are never re-overridden.

`clearAll()` stays as-is (resets filters to empty) and deliberately **does not**
clear the marker, so an intentional clear is respected and will not re-seed on
the next reload.

## Data flow

```
CV sections
  → _gather_profile (summary blob)
  → infer_candidate_level + extract_min_years
  → band/buffer math
  → GET /ingestion/profile-defaults
  → ingestion.service.getProfileFilterDefaults()
  → JobFiltersComponent.ngOnInit seeds chips & years input (once, via marker)
  → existing filter_and_paginate applies them as hard filters
```

## Out of scope (YAGNI)

- No `seniority_level` / `years_experience` fields on `CandidateProfile`, no DB
  migration, no Profile-page UI.
- No change to scoring — match % already uses the profile.
- No re-seeding logic beyond the one-time marker.

## Testing

- **Unit — band math:** each `SeniorityLevel` maps to the correct ±1 clamp;
  `UNKNOWN` → `[]`.
- **Unit — years buffer:** value found → `years + buffer`; absent → `None`;
  buffer read from config.
- **Unit — endpoint:** returns the expected shape with a profile present and with
  no profile (empty/null).
- Existing `test_seniority.py` and `test_candidate_level.py` already cover the
  underlying inference primitives.

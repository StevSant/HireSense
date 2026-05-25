# Application Pipeline Redesign

**Status:** Approved, ready for implementation planning
**Date:** 2026-05-24

## Problem

The product has the right vertical slices (Ingestion, Matching, Optimization, Tracking, Interview) but no spine connecting them. Three concrete pain points:

1. **CV Optimization** asks the user to type the job description, required skills, and missing skills by hand — even when the same job has already been ingested and matched. `MatchResult` already contains `matched_skills` and `missing_skills`, but the optimization page ignores it (the request hard-codes `match_id='manual'`).
2. **`TrackedApplication` is a stub.** It stores `title`, `company`, `url`, `notes`, `status` only. There is no link to the match result, the optimized CV, or the interview prep. The user can't "dig into" an application because there is nothing to dig into.
3. **Interview prep** is an island. It accepts free-form `job_title`/`company`/`description` and is not aware of tracked applications. Newly created applications don't surface there.

## Goals

- A tracked application becomes the **central object** of the pipeline. Job, match, CV optimization, and interview prep all hang off it.
- The optimization page never asks for required/missing skills — they come from the snapshot and the match.
- Applications created anywhere in the app (Ingestion → Track, or pasted-description quick create) immediately surface on the Interview page.
- The user can "dig" into any application via a single detail view, edit each piece, and regenerate any artifact.

## Non-goals

- No multi-user / org concerns — this is single-user.
- No automated CV publishing / submitting to job boards.
- No retroactive backfill of match/optimization/interview-prep for existing tracked rows — only the job snapshot is backfilled. The user re-runs each artifact on demand.

## Architecture: Approach B — application as aggregate with child artifact tables

`TrackedApplication` stays as the metadata row. Four new child tables, each FK → `tracked_applications.id` with `ON DELETE CASCADE`. The application detail endpoint returns the aggregate (app + 1:1 snapshot + latest of each 1:N artifact) in a single response.

### Data model

```
tracked_applications                        (unchanged)
  id, job_id (FK ingestion job, nullable),
  title, company, url, status, notes,
  applied_at, created_at, updated_at

application_job_snapshots                   (NEW, 1:1)
  id (UUID PK)
  application_id (FK, UNIQUE, CASCADE)
  description (text)
  required_skills (JSON list[str])
  source ('ingested' | 'manual' | 'llm_extracted')
  created_at, updated_at

application_matches                         (NEW, 1:N)
  id (UUID PK)
  application_id (FK, CASCADE)
  overall_score (float)
  semantic_score, skill_score, experience_score, language_score (float)
  matched_skills, missing_skills (JSON list[str])
  pros, cons, recommendations (JSON list[str])
  cv_language (str)
  created_at
  INDEX (application_id, created_at DESC)

application_cv_optimizations                (NEW, 1:N)
  id (UUID PK)
  application_id (FK, CASCADE)
  match_id (FK application_matches.id, nullable)
  cv_language (str)
  original_tex (text)
  optimized_tex (text)
  improvement_summary (text)
  changes (JSON — list of section diffs)
  created_at
  INDEX (application_id, created_at DESC)

application_interview_preps                 (NEW, 1:N)
  id (UUID PK)
  application_id (FK, CASCADE)
  competencies_to_probe, technical_topics, negotiation_points (JSON list[str])
  matched_stories (JSON list[{story_id, story_title, relevance}])
  created_at
  INDEX (application_id, created_at DESC)
```

**Why this shape:**
- Job snapshot is 1:1 because there's exactly one "current job description" per application. It's mutable but not versioned — when the user edits it, the row updates in place. (If a history of description edits becomes valuable later, this is a one-table refactor.)
- Match / optimization / interview prep are 1:N because the user will iterate (re-run match after editing skills; try multiple CV versions; regenerate prep after adding stories). Latest is "most recent by `created_at`".
- Snapshot is **frozen** at creation: if the upstream `NormalizedJob` is later purged or modified, the application remains self-contained.

### New bounded context

A new `hiresense/applications/` package with the same shape as the existing contexts:

```
hiresense/applications/
  api/
    routes.py, schemas.py, dependencies.py, provider.py
  domain/
    aggregate.py            (Application aggregate model — wraps snapshot + artifacts)
    models.py               (SQLAlchemy models for the four new tables)
    services.py             (ApplicationService — create, get, list, delete)
    artifact_service.py     (ArtifactService — generate match / opt / prep, persist)
    skill_extractor.py      (LLM-backed required-skill extractor)
  infrastructure/
    repository.py
  ports/
    __init__.py             (ApplicationRepositoryPort)
```

Per the project's `code-style` rule, each class lives in its own file; `__init__.py` re-exports for package-level imports.

The new context **calls into** existing services:
- `MatchingOrchestrator.analyze()` for match generation.
- `CvOptimizer.optimize()` for optimization.
- `InterviewPrepService.prepare()` for interview prep.
- `ProfileService` to read the user's profile (skills, raw_tex, summary).

Existing services don't move. The new aggregate is the orchestrator that calls them and persists the results into the new tables.

### API surface

New routes under `/applications`:

| Method | Path | Purpose |
|---|---|---|
| POST | `/applications` | Create — body is either `{job_id}` (from ingestion) or `{title, company, description, url?}` (manual) |
| GET | `/applications` | List — each row carries `has_match`, `has_optimization`, `has_prep`, `latest_match_score` flags |
| GET | `/applications/{id}` | Full aggregate — app + snapshot + latest match + latest optimization + latest prep + history counts |
| PATCH | `/applications/{id}` | Status, notes (existing tracking semantics) |
| DELETE | `/applications/{id}` | Cascade |
| PUT | `/applications/{id}/job-snapshot` | Edit description and/or required_skills |
| POST | `/applications/{id}/job-snapshot/regenerate-skills` | LLM re-extract skills from current description |
| POST | `/applications/{id}/match` | Generate new match using snapshot + active profile |
| GET | `/applications/{id}/matches` | History (paginated) |
| POST | `/applications/{id}/optimize` | Body `{cv_language, match_id?}` — generate CV optimization |
| GET | `/applications/{id}/optimizations` | History |
| POST | `/applications/{id}/interview-prep` | Generate interview prep |
| GET | `/applications/{id}/interview-preps` | History |

Existing `/tracking/*`, `/matching/analyze`, `/optimization/optimize`, `/interview/prepare` stay during the transition. After the frontend cutover, `/tracking/*` becomes a thin shim that proxies to `/applications`; the others remain as ad-hoc tools accessible only from quick-create paths.

### Skill auto-extraction

`required_skills` is populated **at creation** and updatable on demand:

- **Ingested job**: copy `NormalizedJob.skills` verbatim into the snapshot. `source = 'ingested'`. No LLM call.
- **Manual description**: synchronous LLM call from `POST /applications`. `source = 'llm_extracted'`. If the LLM call fails, the snapshot is still created with `required_skills=[]` and `source = 'manual'`; the user can hit "Regenerate skills" later.
- **User edits description**: snapshot updates in place; `required_skills` is **not** auto-cleared. A separate "Regenerate skills" button calls `/job-snapshot/regenerate-skills`.

`missing_skills` is never typed:
- During match generation: computed as `required_skills − profile.skills` (case-insensitive) and persisted on the `application_matches` row.
- The CV tab reads `missing_skills` from the latest match. If no match exists, the UI shows a prompt to "Run match first".

### Frontend architecture

**New route** `/dashboard/applications/:id` — `ApplicationDetailComponent`:

```
┌──────────────────────────────────────────────────────────┐
│  Software Engineer — Fieldguide          [status ▼]  ✕   │
│  San Francisco, CA · Posted 2026-04-20                   │
├──────────────────────────────────────────────────────────┤
│  Job  │  Match  │  CV  │  Interview                      │
├──────────────────────────────────────────────────────────┤
│  (tab content)                                           │
└──────────────────────────────────────────────────────────┘
```

- **Job tab** — description (editable textarea), required skills as removable chips, "Regenerate skills" button.
- **Match tab** — score breakdown (semantic / skill / experience / language), matched + missing skill chips, pros/cons/recommendations, "Re-run match" button, history dropdown.
- **CV tab** — language picker, "Generate optimization" button (disabled with hint if no match exists), latest result with `Download .tex`, version dropdown listing older optimizations.
- **Interview tab** — "Generate prep" button, competencies / technical topics / negotiation points, matched stories with relevance text, history dropdown.

**Repurposed pages**:

- `/dashboard/tracking` — renamed **Applications**. Same list shape with new badges (`has_match`, `has_optimization`, `has_prep`, latest score). Rows link to `/applications/:id`. A "+ New application" button opens a small dialog: pick an ingested job OR paste title+company+description.
- `/dashboard/optimization` — thin form: "Optimize a CV. Paste a job description, or pick an existing application." Submitting the paste form quick-creates an application and navigates to its CV tab. Removes the standalone manual-skill input that exists today.
- `/dashboard/matching` — removed from main nav; the quick-create flow is the canonical entry point for ad-hoc matching, and "Re-run match" inside the detail view covers per-application matching. The existing component file stays in the codebase as a temporary shim during transition, then deleted.
- `/dashboard/interview` — top section becomes **Applications** list (status filter + "Generate prep" button per row → opens detail view on Interview tab). Story bank component stays below, unchanged. The free-form prep form is removed.

Components, one per file per project code-style:

```
frontend/src/app/pages/applications/
  applications.component.ts                       (list view, replaces tracking)
  application-detail.component.ts
  components/
    application-create-dialog.component.ts
    job-tab.component.ts
    match-tab.component.ts
    cv-tab.component.ts
    interview-tab.component.ts
    skill-chips.component.ts                      (reusable add/remove chips)
    artifact-history-dropdown.component.ts        (reusable for match/opt/prep history)
  models/
    application.model.ts
    application-aggregate.model.ts
    job-snapshot.model.ts
    application-match.model.ts
    cv-optimization.model.ts
    application-interview-prep.model.ts
```

Existing `interview.component.ts` is restructured to use a new `applications-prep-list.component.ts` at the top and keeps the existing `story-bank` section below.

### Pipeline flow

```
Ingestion job ──Track──> Application created
                         │
                         ├── snapshot.source = 'ingested', skills copied from NormalizedJob
                         │
Manual paste ──Quick-Create──> Application created
                               │
                               └── snapshot.source = 'llm_extracted', LLM extracts skills

Application detail view (/applications/:id):
  Job tab        — edit description, regenerate skills
  Match tab      — POST /applications/:id/match  → reads snapshot + profile, persists match
  CV tab         — POST /applications/:id/optimize → reads snapshot + latest match + profile.raw_tex
  Interview tab  — POST /applications/:id/interview-prep → reads snapshot + story bank
                   ↑ also reachable from /dashboard/interview applications list
```

### Migration (Alembic)

One revision creates the four new tables and runs a data migration:

1. Create `application_job_snapshots`, `application_matches`, `application_cv_optimizations`, `application_interview_preps`.
2. For each existing `tracked_applications` row:
   - If `job_id IS NOT NULL` and the referenced `NormalizedJob` exists, insert a snapshot with `description = NormalizedJob.description`, `required_skills = NormalizedJob.skills`, `source = 'ingested'`.
   - Otherwise insert an empty snapshot (`description=''`, `required_skills=[]`, `source = 'manual'`).
3. No backfill for match/optimization/interview prep — those are regenerated on demand.

### Error handling and edge cases

- **No active profile** when running match or optimize → 400 with a clear message; UI surfaces "Set up a profile first" with a link to `/dashboard/profile`.
- **No match when optimizing** → 400; UI shows "Run match first" prompt instead of the optimize button.
- **No stories when generating interview prep** → still allowed; the prep just returns empty `matched_stories`.
- **LLM skill extraction fails** at create-time → application still created, `required_skills=[]`, `source='manual'`. UI shows a "Skills could not be extracted automatically — add manually or click Regenerate" banner.
- **Concurrent regenerate calls** → not guarded at DB level; the latest write wins for snapshot, and each artifact endpoint inserts a new row, so duplicates are fine.
- **Deleting an application** cascades all four child tables.
- **Deleting an ingestion job** while an application references it → the application's `job_id` becomes a dangling FK (the ingestion side already allows this). The snapshot is frozen so functionality is unaffected. Add `ON DELETE SET NULL` on `tracked_applications.job_id` if not already configured.

### Testing

- Unit tests for `ApplicationService` (create from ingested, create from manual, edit snapshot, regenerate skills).
- Unit tests for `ArtifactService` (generate match/opt/prep, history listing).
- Integration test: full pipeline — ingest → track → match → optimize → prep — asserting each artifact is persisted with correct FKs.
- Migration test on a fixture DB containing a `tracked_applications` row with and without `job_id`; assert snapshots backfilled correctly.
- Frontend: Cypress or Playwright walk-through of the detail view's four tabs.

### Open questions

None blocking. Items to revisit during planning:
- Where the `SkillExtractor` lives — `applications/domain/` vs a shared `nlp/` module — depends on whether other contexts need it.
- Whether to add a thin DB-level `latest_*` materialized view for the list endpoint, or just compute the aggregates in the service (start with the latter; optimize only if needed).

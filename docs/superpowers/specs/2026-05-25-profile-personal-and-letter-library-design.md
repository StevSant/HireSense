# Personal Details Edit + Cover Letter Library — Design (Phase 2)

**Date:** 2026-05-25
**Phase:** 2 of 3 (extends [[2026-05-25-profile-hub-and-sidebar-design]])
**Scope:** Backend (migration + 2 endpoints) + frontend wiring for the two stub tabs introduced in Phase 1.

## Problem

Phase 1 shipped the Profile-as-hub frame with two tabs — Personal details and Cover letters — that contain "Coming soon" stubs. Phase 2 fills both:

- **Personal details** today shows only CV-parsed fields. The user wants to edit/add manual fields (LinkedIn, GitHub, portfolio, plus a way to override the parsed name/location when the CV is wrong).
- **Cover letters** today points at the per-job Apply flow. The user wants a cross-application Library — every letter they've generated, in one searchable view, so they can copy/reuse text without digging into each application.

## Non-goals (this phase)

- No cover letter templates (that's Phase 3).
- No PDF download from the Library (PDFs are tightly coupled to the application context — keeping that in Applications).
- No edit-in-place for cover letter body (copying out is the workflow; if the user wants to regenerate, they go back to Applications).
- No user authentication scoping (the app currently has a single tenant — same as Phase 1).
- No URL link previews / OG-image fetching.

## Design

### Backend

#### Migration 007: `profiles` manual override columns

Add five nullable columns to the `profiles` table:

| Column | Type | Why |
|---|---|---|
| `name_override` | `String(255)` | When the LaTeX parser pulls the wrong name (e.g. picks up a header label) |
| `location_override` | `String(255)` | Same — and lets the user put a more precise city/country than the CV phrasing |
| `linkedin_url` | `String(500)` | Not parseable from most CVs reliably |
| `github_url` | `String(500)` | Same |
| `portfolio_url` | `String(500)` | Same |

All five default `NULL`. Existing rows unaffected.

#### `CandidateProfile` (pydantic) — gains the five fields

```python
class CandidateProfile(BaseModel):
    # ... existing fields ...
    name_override: str | None = None
    location_override: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
```

Service layer adds an `effective_name` / `effective_location` notion when needed (frontend can also compute this — see below). We'll keep the *raw* override fields in the API response so the UI can show "currently overridden" state when editing.

#### `PATCH /profile/{profile_id}` endpoint

```python
class ProfilePatchRequest(BaseModel):
    name_override: str | None = None
    location_override: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
```

Semantics:
- Each field is **explicitly nullable** — sending `null` clears the field, omitting the key leaves it unchanged. We use pydantic's `model_fields_set` to distinguish "set to null" from "not provided".
- Returns the full updated `CandidateProfile`.
- 404 if no profile with that id.
- 422 if any URL field fails basic format validation (must look like `http(s)://...` — light validation only, no DNS lookup).

`ProfileRepository.update_manual_fields(profile_id, fields: dict)` is the new repo method; service wires it through.

#### `GET /applications/cover-letters` — cross-app library

Returns every cover letter ever generated, joined with parent application info, newest first.

```python
class CoverLetterLibraryItem(BaseModel):
    id: uuid.UUID            # cover letter id
    application_id: uuid.UUID
    job_title: str           # from tracked_applications.title
    company: str             # from tracked_applications.company
    body: str
    tone: str
    application_status: str  # from tracked_applications.status (so UI can badge "applied")
    created_at: datetime
```

`ApplicationRepository.list_all_cover_letters_with_apps()` is the new repo method. SQL is a simple inner-join on `application_cover_letters` × `tracked_applications`, ordered `created_at DESC`. Returns a list of tuples of `(ApplicationCoverLetter, TrackedApplication)` that the service maps to view models.

No pagination in Phase 2 — current user has probably <50 letters max. If the dataset grows past ~500 we'll add it.

#### Tests (backend)

- `tests/profile/test_patch_manual_fields.py`: PATCH updates each field; null clears it; omitted keys preserve; 404 on unknown id; 422 on invalid URL.
- `tests/applications/test_cover_letter_library.py`: empty case → `[]`; multiple letters across multiple apps → newest first; deletion cascade preserved (deleting an app removes its letters from the library).

### Frontend

#### Profile service (`profile.service.ts`) gains:

- `updateProfile(id, patch)` — PATCH wrapper, returns `Observable<CandidateProfile>` and updates the local profile signal on success.

#### Applications service (`applications.service.ts`) gains:

- `listAllCoverLetters()` — returns `Observable<CoverLetterLibraryItem[]>`.

#### `CandidateProfile` interface (frontend model) gains the five new fields. A small derived helper on the Profile component:

```typescript
effectiveName = computed(() => this.profile()?.name_override || this.profile()?.name || '');
effectiveLocation = computed(() => this.profile()?.location_override || this.profile()?.location || '');
```

These are used in the read view. The avatar's first-letter calculation switches to `effectiveName`.

#### Personal details tab — Edit mode

Add an "Edit" button on the read view. Click → swap to a form with five inputs:
- Name (placeholder: parsed name from CV; saving an empty string = clear override)
- Location (placeholder: parsed location)
- LinkedIn URL (`type=url`)
- GitHub URL (`type=url`)
- Portfolio URL (`type=url`)

Save / Cancel buttons. On Save: call `updateProfile(...)`. On success: exit edit mode, refresh view. Errors surface inline.

Read view also gains three new rows when set: LinkedIn, GitHub, Portfolio (each rendered as a clickable link with the URL hostname as label, e.g. `linkedin.com/in/bryan`). If a URL field is unset, the row is omitted.

The existing "Coming soon — Manual fields" card is **removed** (it's now shipped).

#### Cover letters tab — Library list

Replace the "Library — Coming soon" stub with a real list:

Each item is a card showing:
- Job title + company (header)
- Application status badge (color-coded — at minimum highlight `applied`)
- Tone badge
- Created-at timestamp (relative: "3 days ago")
- First 2-3 lines of the body, truncated with ellipsis
- Two actions: **Copy body** (clipboard) and **Open application** (routerLink to `/dashboard/applications/{application_id}`)

On the Cover letters tab, the order is now:
1. "Generated per job" explainer (kept from Phase 1, restated as "Generate a new one")
2. **Library** (new — replaces stub)
3. "Templates — Coming soon" (kept for Phase 3 signposting)

Empty Library shows: "You haven't generated any cover letters yet. Open an application and use the Apply tab to create your first one."

#### Tests (frontend)

None added. Project has no frontend test infrastructure; introducing it for these straightforward services would be Phase-2.5 scope creep. Verification via build + manual browser checks per Phase 1 pattern.

## Files touched

**Create:**
- `backend/alembic/versions/007_add_profile_manual_fields.py`
- `backend/tests/profile/test_patch_manual_fields.py`
- `backend/tests/applications/test_cover_letter_library.py`

**Modify (backend):**
- `backend/src/hiresense/profile/domain/models.py` — add 5 columns to `Profile`, 5 fields to `CandidateProfile`
- `backend/src/hiresense/profile/infrastructure/repository.py` — `update_manual_fields()`
- `backend/src/hiresense/profile/domain/services.py` — `update_profile()` orchestration
- `backend/src/hiresense/profile/api/routes.py` — `PATCH /{profile_id}` endpoint + request model
- `backend/src/hiresense/applications/domain/aggregate.py` — `CoverLetterLibraryItem` view model
- `backend/src/hiresense/applications/infrastructure/repository.py` — `list_all_cover_letters_with_apps()`
- `backend/src/hiresense/applications/domain/application_service.py` — `list_all_cover_letters()` service method
- `backend/src/hiresense/applications/api/routes.py` — `GET /cover-letters` endpoint

**Modify (frontend):**
- `frontend/src/app/pages/profile/models/candidate-profile.model.ts` — 5 new optional fields
- `frontend/src/app/pages/applications/models/cover-letter-library-item.model.ts` (CREATE) — new interface
- `frontend/src/app/core/services/profile.service.ts` — `updateProfile()`
- `frontend/src/app/core/services/applications.service.ts` — `listAllCoverLetters()`
- `frontend/src/app/pages/profile/profile.component.ts` — edit-mode signals, library data signal, save/cancel handlers, copy-to-clipboard, time formatter
- `frontend/src/app/pages/profile/profile.component.html` — Personal details Edit mode + Library list
- `frontend/src/app/pages/profile/profile.component.scss` — edit form + library item styles

**Delete:** None.

## Testing

- Backend: pytest covers the new endpoints. Run `cd backend && uv run pytest`.
- Frontend: production build + manual browser flow (upload CV → Personal details → Edit → fill fields → Save → see them on read view; generate a letter in Applications → Profile → Cover letters → Library shows it).

## Rollout

Single PR stacked on Phase 1 (`feat/profile-personal-and-letter-library`). When Phase 1 merges, rebase this branch onto main. Migration is forward-only safe (adds nullable columns), but always run `alembic upgrade head` after pulling.

## Phase 3 — out of scope, noted for continuity

**Cover letter templates:**
- New `cover_letter_templates` table (id, name, body, tone, language, created_at, updated_at).
- CRUD endpoints under `/profile/cover-letter-templates`.
- `cover_letter_generator.py` gains optional `template_id` — when provided, the LLM prompt is seeded with the template as a stylistic example.
- Profile → Cover letters tab gains a "Templates" section (replaces the Phase 2 stub) with create/edit/delete.
- The per-job Apply UI gains a "Use template" dropdown that passes `template_id` to the existing generate endpoint.

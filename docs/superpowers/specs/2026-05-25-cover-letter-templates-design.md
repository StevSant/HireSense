# Cover Letter Templates — Design (Phase 3)

**Date:** 2026-05-25
**Phase:** 3 of 3 (extends [[2026-05-25-profile-personal-and-letter-library-design]])
**Scope:** Reusable cover letter templates the user can pick from when generating per-job letters.

## Problem

The per-job generator is a black box: each cover letter comes out in a slightly different voice depending on the LLM's mood. Users want consistency — "always sign off this way", "always open with this hook", "match the tone of this letter I wrote myself". Templates give them stylistic anchors without losing the per-job tailoring.

## Non-goals

- No template marketplace / sharing across users (single-tenant app).
- No "regenerate using template" on already-saved letters — templates only affect *new* generations.
- No rich-text editing (plain text body, like the rest of the cover letter system).
- No automatic template suggestion based on past letters.

## Design

### Data

**`cover_letter_templates`** (new table, migration 008):

| Column | Type | Notes |
|---|---|---|
| `id` | `Uuid` | primary key, default `gen_random_uuid()` |
| `name` | `String(120)` | user-visible label (e.g. "Concise, technical") |
| `body` | `Text` | the template text — used as a stylistic example, not literal |
| `tone` | `String(20)` | default `professional`; same vocabulary as existing letters |
| `language` | `String(10)` | default `en`; matches existing language tags |
| `created_at` | `DateTime` | server default `now()` |
| `updated_at` | `DateTime` | server default `now()`, on update `now()` |

Index on `created_at` for stable list ordering.

### Backend endpoints

All under `/profile/cover-letter-templates` (under the profile router because templates belong to the user's *profile assets*, alongside their CVs):

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `` | — | `list[CoverLetterTemplateView]` (newest first) |
| POST | `` | `{name, body, tone?, language?}` | `CoverLetterTemplateView` (201) |
| PATCH | `/{id}` | partial of above | `CoverLetterTemplateView` |
| DELETE | `/{id}` | — | 204 |

422 if `name` or `body` empty/whitespace. 404 on unknown id.

### Generator integration

`CoverLetterGenerator.generate()` gains an optional `template_body: str | None = None`. When set, the user prompt appends:

> Stylistic reference (a previous cover letter the candidate liked — match its voice and structure, do NOT copy text verbatim):
> ---
> {template_body}
> ---

`ApplyService.generate_cover_letter()` gains `template_id: uuid.UUID | None = None`. When provided, fetches the template, passes its body to the generator, AND uses the template's `tone` as a default if no explicit tone was passed in.

Existing `POST /applications/{id}/cover-letter` route's `GenerateCoverLetterRequest` gains `template_id: uuid.UUID | None = None`.

### Frontend

**New service** `cover-letter-templates.service.ts` (under `core/services/`) with the four CRUD methods + a local signal cache for the list.

**Profile → Cover letters tab gets a Templates section** between the existing Library section and the (now-removed) Templates "Coming soon" stub. Each template card shows name, tone badge, language badge, body preview (3 lines), Edit / Delete buttons. A "New template" button at the section header opens a form (name, tone select, language select, body textarea).

**Apply tab** (`apply-tab.component`) gets a "Template" `<select>` below the existing tone/language controls, populated from the templates service (filtered to the current CV language). When set, passes `template_id` in the generate call.

### Tests

Backend:
- Route tests for the 4 CRUD endpoints using `FakeTemplateService` (existing route-test pattern with `dependency_overrides`).
- One generator test that asserts the prompt contains the template body when one is passed.

Frontend: build verification only (matches Phase 1 & 2 convention).

## Files touched

**Create (backend):**
- `backend/alembic/versions/008_create_cover_letter_templates.py`
- `backend/src/hiresense/profile/cover_letter_templates/__init__.py`
- `backend/src/hiresense/profile/cover_letter_templates/models.py` — SQLAlchemy + Pydantic view + request
- `backend/src/hiresense/profile/cover_letter_templates/repository.py`
- `backend/src/hiresense/profile/cover_letter_templates/service.py`
- `backend/src/hiresense/profile/cover_letter_templates/routes.py`
- `backend/src/hiresense/profile/cover_letter_templates/dependencies.py`
- `backend/tests/unit/profile/test_cover_letter_template_routes.py`
- `backend/tests/unit/applications/test_cover_letter_generator_with_template.py`

**Modify (backend):**
- `backend/src/hiresense/main.py` — include the new templates router
- `backend/src/hiresense/applications/domain/cover_letter_generator.py` — accept `template_body`, inject into prompt
- `backend/src/hiresense/applications/domain/apply_service.py` — accept `template_id`, fetch + plumb through
- `backend/src/hiresense/applications/api/routes.py` + `schemas.py` — accept `template_id` in the generate request

**Create (frontend):**
- `frontend/src/app/pages/profile/models/cover-letter-template.model.ts`
- `frontend/src/app/core/services/cover-letter-templates.service.ts`

**Modify (frontend):**
- `frontend/src/app/pages/profile/profile.component.ts` — template state + CRUD handlers
- `frontend/src/app/pages/profile/profile.component.html` — Templates section replaces the Phase 2 stub
- `frontend/src/app/pages/profile/profile.component.scss` — template card styles
- `frontend/src/app/pages/applications/components/apply-tab.component.ts` + `.html` — template dropdown
- `frontend/src/app/core/services/applications.service.ts` — `generateCoverLetter()` gains optional `template_id`

## Testing

- Backend: pytest covers route + generator-prompt-injection. Run `uv run python -m pytest`.
- Frontend: `npx ng build`. Manual browser walk: create template → see in Templates section → generate letter from Applications with template selected → verify resulting letter has noticeable stylistic similarity.

## Rollout

Single PR stacked on Phase 2 (`feat/cover-letter-templates` off `feat/profile-personal-and-letter-library`). Migration 008 is forward-only safe (new isolated table). Rebase onto main once Phases 1 + 2 merge.

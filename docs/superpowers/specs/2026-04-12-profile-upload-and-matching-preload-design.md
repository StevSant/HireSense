# Profile File Upload & Matching Preload

## Context

HireSense's profile feature only accepts pasted LaTeX (.tex) content, and the matching page requires manually typing job descriptions, CV summaries, and skills every time. Both create unnecessary friction. The user has CVs in various formats and ingested job data already in the system — these should be leveraged automatically.

This design adds PDF/LaTeX file upload to the profile page and preloads matching data from the stored profile and ingested jobs.

## Scope

Two improvements, unified by profile persistence as the shared foundation:

1. **Profile file upload** — accept PDF and .tex file uploads, parse with LLM (PDF) or existing regex parser (.tex)
2. **Matching preloading** — auto-fill CV data from stored profile, show ingested jobs in a dropdown for selection

## 1. Profile File Upload

### Backend

**New endpoint:** `POST /profile/upload-file`
- Accepts `multipart/form-data`: file (PDF or .tex) + language field
- Routes to `PDFParser` or `LaTeXParser` based on file extension
- Saves uploaded file to `cvs/originals/`
- Returns `CandidateProfile`

**New class:** `PDFParser` (`profile/domain/pdf_parser.py`)
- Extracts raw text from PDF using PyMuPDF (`pymupdf` package)
- Sends extracted text to configured LLM with a structured prompt
- LLM returns: name, email, phone, location, sections (name + content pairs), skills
- Parses LLM response into `ParsedCV` dataclass (same as LaTeXParser output)

**Modified class:** `ProfileService` (`profile/domain/services.py`)
- New method: `parse_file_and_create(file_bytes: bytes, filename: str, language: str) -> CandidateProfile`
- Checks extension: `.pdf` routes to PDFParser, `.tex` routes to LaTeXParser
- Saves file to `cvs/originals/{profile_id}_{filename}`
- Stores profile via repository (see Section 2)

**New dependency:** `pymupdf` added to `pyproject.toml`

### Frontend

**Modified component:** `ProfileComponent`
- Two tabs: "Upload File" | "Paste LaTeX"
- Upload File tab: drag-and-drop zone accepting `.pdf` and `.tex`, language selector, upload button
- Paste LaTeX tab: existing textarea (unchanged behavior)
- New signal: `activeTab` to toggle between tabs
- New signal: `selectedFile` for the file reference

**Modified service:** `ProfileService`
- New method: `uploadFile(file: File, language: string): Observable<CandidateProfile>`
- Sends `FormData` via POST to `/profile/upload-file`

### Data model

No changes to `CandidateProfile` — existing fields (name, email, phone, location, sections, raw_tex, language, skills, embedding) cover all extracted data. For PDF uploads, `raw_tex` stores the extracted plain text instead of LaTeX.

## 2. Profile Persistence

### Backend

**New migration:** `004_create_profiles.py`
- Table: `profiles`
- Columns: `id (PK, varchar)`, `name`, `email`, `phone`, `location`, `sections (JSONB)`, `raw_tex (TEXT)`, `language`, `skills (JSONB)`, `embedding (vector, nullable)`, `created_at (timestamp)`

**New class:** `ProfileRepository` (`profile/infrastructure/repository.py`)
- Async SQLAlchemy repository
- Methods: `save(profile)`, `get(profile_id)`, `get_latest() -> CandidateProfile | None`
- Follows same pattern as existing `TrackingRepository`

**Modified class:** `ProfileService`
- Constructor accepts `ProfileRepository`
- `parse_and_create` and `parse_file_and_create` persist via repository instead of in-memory dict
- Remove `_profiles` dict

**New endpoint:** `GET /profile/current`
- Returns the most recently created profile
- Returns 404 if no profile exists
- Single-user app, so "current" = latest by `created_at`

### Frontend

**Modified service:** `ProfileService`
- New method: `getCurrentProfile(): Observable<CandidateProfile>`
- Calls `GET /profile/current`

**Modified component:** `ProfileComponent`
- On init, calls `getCurrentProfile()`
- If profile exists: shows profile view immediately (skip upload form)
- If not: shows upload form

## 3. Matching Page Preloading

### Backend

**New endpoint:** `GET /ingestion/jobs`
- Returns list of `NormalizedJob` from `IngestionOrchestrator.list_jobs()` (method already exists)
- Simple read from in-memory store, no new logic needed

### Frontend

**Modified service:** `IngestionService`
- New method: `listJobs(): Observable<NormalizedJob[]>`
- Calls `GET /ingestion/jobs`

**Modified component:** `MatchingComponent`
- On init:
  1. `ProfileService.getCurrentProfile()` -> auto-fills `cvSummary` (concatenated section content) and `cvSkills` (from skills array, joined with commas)
  2. `IngestionService.listJobs()` -> populates a job selector dropdown
- New signal: `jobs` holding the ingested job list
- New signal: `selectedJob` for the currently selected job
- When a job is selected from dropdown: auto-fills `jobDescription` (from `description`) and `jobSkills` (from `skills`, joined with commas)
- Dropdown includes a "Manual entry" option that clears auto-fill and restores blank fields
- All auto-filled fields remain editable

### UX Flow

1. Navigate to Matching page
2. CV summary and skills auto-populate from stored profile
3. Job dropdown shows ingested jobs (title + company)
4. Select a job -> job description and skills auto-fill
5. Click "Analyze Match" — no manual typing needed
6. Or pick "Manual entry" to type everything by hand

## Files to Create

| File | Purpose |
|------|---------|
| `backend/src/hiresense/profile/domain/pdf_parser.py` | PDF text extraction + LLM structured parsing |
| `backend/src/hiresense/profile/infrastructure/repository.py` | SQLAlchemy async profile persistence |
| `backend/alembic/versions/004_create_profiles.py` | Database migration for profiles table |

## Files to Modify

| File | Changes |
|------|---------|
| `backend/pyproject.toml` | Add `pymupdf` dependency |
| `backend/src/hiresense/profile/domain/services.py` | Add `parse_file_and_create`, switch to repository |
| `backend/src/hiresense/profile/api/routes.py` | Add `upload-file` and `current` endpoints |
| `backend/src/hiresense/profile/api/provider.py` | Wire repository into provider |
| `backend/src/hiresense/profile/api/dependencies.py` | Add repository dependency if needed |
| `backend/src/hiresense/main.py` | Pass repository + LLM to ProfileService, wire new provider |
| `backend/src/hiresense/ingestion/api/routes.py` | Add `GET /jobs` endpoint |
| `frontend/src/app/core/services/profile.service.ts` | Add `uploadFile()` and `getCurrentProfile()` |
| `frontend/src/app/core/services/ingestion.service.ts` | Add `listJobs()` |
| `frontend/src/app/pages/profile/profile.component.ts` | Tabbed UI, file upload, load existing profile on init |
| `frontend/src/app/pages/profile/profile.component.html` | Tab layout, drag-and-drop zone |
| `frontend/src/app/pages/profile/profile.component.scss` | Tab and dropzone styles |
| `frontend/src/app/pages/matching/matching.component.ts` | Preload profile + jobs, job selector logic |
| `frontend/src/app/pages/matching/matching.component.html` | Job dropdown, auto-filled fields |
| `frontend/src/app/pages/matching/matching.component.scss` | Dropdown styles |

## Existing Code to Reuse

- `LaTeXParser` (`profile/domain/latex_parser.py`) — existing .tex parsing, no changes needed
- `SkillExtractor` (`profile/domain/skill_extractor.py`) — existing skill extraction
- `IngestionOrchestrator.list_jobs()` (`ingestion/domain/services.py:92`) — already returns `list[NormalizedJob]`
- `TrackingRepository` pattern (`tracking/infrastructure/`) — model for `ProfileRepository`
- `ProfileProvider` pattern (`profile/api/provider.py`) — extend for repository
- `cvs/originals/` directory — already exists for file storage
- LLM port (`ports/llm.py`) — use configured LLM for PDF parsing

## Frontend Design Quality

The profile upload and matching pages must be polished and elegant, not just functional. During implementation:

- Use the `frontend-design` skill for creating the UI components (tabbed upload, drag-and-drop zone, job selector dropdown)
- After each UI implementation step, use Playwright to screenshot and visually verify the result in a real browser
- Iterate multiple rounds on the design — refine spacing, colors, typography, hover states, transitions, and responsive behavior until the UI feels production-grade
- Match the existing Indigo (#4f46e5) color scheme and card-based layout already established in the app
- The drag-and-drop zone should have clear visual states: default, hover/drag-over, file-selected, uploading, success/error
- The job selector dropdown should feel native and clean, not like an afterthought bolted onto the form

## Verification

1. **Profile file upload (PDF):**
   - Upload a PDF CV via the drag-and-drop zone
   - Verify structured profile data is displayed (name, email, skills, sections)
   - Verify file saved to `cvs/originals/`
   - Restart backend, navigate to profile — verify profile loads from DB

2. **Profile file upload (.tex):**
   - Switch to "Paste LaTeX" tab, paste .tex content
   - Verify existing parsing still works identically
   - Also test uploading a .tex file via the file upload tab

3. **Profile persistence:**
   - Upload a profile, restart backend
   - Navigate to profile page — should show existing profile without re-uploading
   - Upload a new profile — should replace the displayed one

4. **Matching preloading:**
   - Ensure a profile exists and jobs have been ingested
   - Navigate to matching page
   - Verify CV summary and skills are auto-filled from profile
   - Verify job dropdown is populated with ingested jobs
   - Select a job — verify job description and skills populate
   - Select "Manual entry" — verify fields clear for manual input
   - Run an analysis with preloaded data — verify results display correctly

5. **Visual polish (iterative):**
   - Use Playwright to screenshot each page after implementation
   - Review for spacing, alignment, color consistency, hover states, transitions
   - Iterate at least 2-3 rounds of visual refinement per page
   - Verify responsive behavior at common viewport sizes

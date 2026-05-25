# Personal Details Edit + Cover Letter Library — Implementation Plan (Phase 2)

> **For agentic workers:** Use superpowers:executing-plans (inline, this session). Steps use `- [ ]` checkboxes.

**Goal:** Wire backend (migration + 2 endpoints) and frontend for the Personal details Edit mode and the Cover letter Library, replacing the Phase 1 "Coming soon" stubs.

**Architecture:**
- Backend: add 5 nullable columns to `profiles` for manual overrides + URLs, expose via `PATCH /profile/{id}`. Add cross-app `GET /applications/cover-letters` aggregator joining `application_cover_letters` × `tracked_applications`.
- Frontend: add `updateProfile()` and `listAllCoverLetters()` services, swap the two stub cards for real Edit form and Library list, plus a small `effectiveName/Location` computed for the read view.

**Tech Stack:** Backend — FastAPI + SQLAlchemy + Alembic + pytest (uv). Frontend — Angular 21 + signals + RouterLink.

**Spec:** `docs/superpowers/specs/2026-05-25-profile-personal-and-letter-library-design.md`

---

## Task 1: Alembic migration 007 — profile manual fields

**Files:**
- Create: `backend/alembic/versions/007_add_profile_manual_fields.py`

- [ ] **Step 1: Write the migration**

```python
"""add manual override + URL fields to profiles

Revision ID: 007
Revises: 006
Create Date: 2026-05-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("name_override", sa.String(255), nullable=True))
    op.add_column("profiles", sa.Column("location_override", sa.String(255), nullable=True))
    op.add_column("profiles", sa.Column("linkedin_url", sa.String(500), nullable=True))
    op.add_column("profiles", sa.Column("github_url", sa.String(500), nullable=True))
    op.add_column("profiles", sa.Column("portfolio_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "portfolio_url")
    op.drop_column("profiles", "github_url")
    op.drop_column("profiles", "linkedin_url")
    op.drop_column("profiles", "location_override")
    op.drop_column("profiles", "name_override")
```

- [ ] **Step 2: Run the migration**

```bash
cd backend && uv run alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade 006 -> 007, add manual override + URL fields to profiles`. No errors.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/007_add_profile_manual_fields.py
git commit -m "feat(db): migration 007 — add profile manual-override + URL fields"
```

---

## Task 2: Profile domain — SQLAlchemy + Pydantic + repo

**Files:**
- Modify: `backend/src/hiresense/profile/domain/models.py`
- Modify: `backend/src/hiresense/profile/infrastructure/repository.py`

- [ ] **Step 1: Add the 5 columns to `Profile` SQLAlchemy model**

In `backend/src/hiresense/profile/domain/models.py`, add to the `Profile` class definition (after the `original_filename` column, before `created_at`):

```python
    name_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

- [ ] **Step 2: Extend `CandidateProfile` pydantic model**

In the same file, after the `embedding` field of `CandidateProfile`, add:

```python
    name_override: str | None = None
    location_override: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
```

- [ ] **Step 3: Add `update_manual_fields` to `ProfileRepository`**

In `backend/src/hiresense/profile/infrastructure/repository.py`, add this method to `ProfileRepository`:

```python
    def update_manual_fields(self, profile_id: uuid.UUID, fields: dict[str, str | None]) -> Profile | None:
        allowed = {"name_override", "location_override", "linkedin_url", "github_url", "portfolio_url"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown profile field(s): {sorted(unknown)}")
        with self._session_factory() as session:
            profile = session.get(Profile, profile_id)
            if profile is None:
                return None
            for key, value in fields.items():
                setattr(profile, key, value)
            session.commit()
            session.refresh(profile)
            return profile
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/profile/domain/models.py backend/src/hiresense/profile/infrastructure/repository.py
git commit -m "feat(profile): add manual override fields + repo update method"
```

---

## Task 3: Profile service + PATCH endpoint

**Files:**
- Modify: `backend/src/hiresense/profile/domain/services.py`
- Modify: `backend/src/hiresense/profile/api/routes.py`

- [ ] **Step 1: Inspect the existing `ProfileService` and find where `CandidateProfile` is constructed from a `Profile` ORM row** (likely a `_to_view` helper or similar). Note its method name.

```bash
grep -n "CandidateProfile(" backend/src/hiresense/profile/domain/services.py | head -5
```

- [ ] **Step 2: Add the view mapping for the new fields**

In `backend/src/hiresense/profile/domain/services.py`, locate the function/method that constructs a `CandidateProfile` from a `Profile` row. Add the five new fields to the construction (mirror the column names):

```python
        return CandidateProfile(
            # ... existing fields ...
            name_override=profile.name_override,
            location_override=profile.location_override,
            linkedin_url=profile.linkedin_url,
            github_url=profile.github_url,
            portfolio_url=profile.portfolio_url,
        )
```

(If there are multiple construction sites, update all of them.)

- [ ] **Step 3: Add `update_profile` service method**

In the same file, on the `ProfileService` class:

```python
    async def update_profile(self, profile_id: uuid.UUID, fields: dict[str, str | None]) -> CandidateProfile | None:
        profile = self._repo.update_manual_fields(profile_id, fields)
        if profile is None:
            return None
        return self._to_view(profile)  # use whatever the existing helper is called
```

Replace `self._to_view(profile)` with the actual helper name discovered in Step 1.

- [ ] **Step 4: Add the PATCH route + request model**

In `backend/src/hiresense/profile/api/routes.py`, **after** the `UploadCVRequest` class, add:

```python
class ProfilePatchRequest(BaseModel):
    name_override: str | None = None
    location_override: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
```

Then add the route (place it after `get_profile` near the end of the file):

```python
import uuid as uuid_mod  # add to existing imports if not present


@router.patch("/{profile_id}", response_model=CandidateProfile)
async def update_profile(
    profile_id: uuid_mod.UUID,
    body: ProfilePatchRequest,
    service: Annotated[object, Depends(get_profile_service)],
) -> CandidateProfile:
    # Only forward fields explicitly set in the request — preserves "omitted = no change".
    fields = body.model_dump(exclude_unset=True)
    for key, value in list(fields.items()):
        if key.endswith("_url") and value is not None:
            value = value.strip()
            if value and not (value.startswith("http://") or value.startswith("https://")):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{key} must start with http:// or https://",
                )
            fields[key] = value or None
    try:
        profile = await service.update_profile(profile_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile
```

- [ ] **Step 5: Quick smoke test of the endpoint**

```bash
cd backend && uv run uvicorn hiresense.main:app --port 8000 &
sleep 2
# Get a profile id (will need to upload first if none exists — skip this curl if no profile)
curl -s http://localhost:8000/profile/current | python -c "import json,sys; d=json.load(sys.stdin); print(d.get('id'))"
# (Manually run a PATCH with that id to verify shape)
kill %1
```

If no profile exists yet, skip this step — the endpoint will be exercised via the tests in Task 4.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/profile/domain/services.py backend/src/hiresense/profile/api/routes.py
git commit -m "feat(profile): PATCH /profile/{id} for manual fields"
```

---

## Task 4: Tests for PATCH /profile/{id}

**Files:**
- Create: `backend/tests/profile/test_patch_manual_fields.py`

- [ ] **Step 1: Find the existing profile test pattern** to learn how the test client + db fixtures are wired:

```bash
ls backend/tests/profile/ 2>/dev/null
find backend/tests -name 'conftest.py' -type f | head -3
```

- [ ] **Step 2: Write the test file**

Read one of the existing profile or applications test files to understand the test-client fixture, then write `backend/tests/profile/test_patch_manual_fields.py` covering:

```python
"""Tests for PATCH /profile/{id} — manual override fields."""
from __future__ import annotations

import pytest

# Reuse whatever client + db fixtures exist in tests/conftest.py
# (Pattern: `client` fixture for httpx TestClient, `db_session` for direct ORM access.)


def _upload_minimal_profile(client) -> str:
    """Helper: create a profile via the existing upload endpoint, return its id."""
    resp = client.post("/profile/upload", json={"tex_content": r"\section{Skills}\nPython", "language": "en"})
    assert resp.status_code == 200
    return resp.json()["id"]


def test_patch_sets_each_field(client) -> None:
    profile_id = _upload_minimal_profile(client)
    resp = client.patch(
        f"/profile/{profile_id}",
        json={
            "name_override": "Bryan P.",
            "location_override": "Quito, Ecuador",
            "linkedin_url": "https://linkedin.com/in/bryan",
            "github_url": "https://github.com/bryan",
            "portfolio_url": "https://bryan.dev",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name_override"] == "Bryan P."
    assert body["location_override"] == "Quito, Ecuador"
    assert body["linkedin_url"] == "https://linkedin.com/in/bryan"
    assert body["github_url"] == "https://github.com/bryan"
    assert body["portfolio_url"] == "https://bryan.dev"


def test_patch_omitted_field_preserved(client) -> None:
    profile_id = _upload_minimal_profile(client)
    client.patch(f"/profile/{profile_id}", json={"linkedin_url": "https://linkedin.com/in/bryan"})
    # Send another patch that does NOT mention linkedin_url
    resp = client.patch(f"/profile/{profile_id}", json={"github_url": "https://github.com/bryan"})
    body = resp.json()
    assert body["linkedin_url"] == "https://linkedin.com/in/bryan"  # preserved
    assert body["github_url"] == "https://github.com/bryan"


def test_patch_null_clears_field(client) -> None:
    profile_id = _upload_minimal_profile(client)
    client.patch(f"/profile/{profile_id}", json={"linkedin_url": "https://linkedin.com/in/bryan"})
    resp = client.patch(f"/profile/{profile_id}", json={"linkedin_url": None})
    assert resp.json()["linkedin_url"] is None


def test_patch_rejects_non_http_url(client) -> None:
    profile_id = _upload_minimal_profile(client)
    resp = client.patch(f"/profile/{profile_id}", json={"linkedin_url": "ftp://nope.com"})
    assert resp.status_code == 422
    assert "http" in resp.json()["detail"].lower()


def test_patch_unknown_profile_404(client) -> None:
    resp = client.patch("/profile/00000000-0000-0000-0000-000000000000", json={"name_override": "x"})
    assert resp.status_code == 404
```

If the test fixture pattern differs (e.g., async client, factory fixtures), adapt syntax accordingly — the assertions stay the same.

- [ ] **Step 3: Run the tests**

```bash
cd backend && uv run pytest tests/profile/test_patch_manual_fields.py -v
```

Expected: 5 passed.

If any test fails for a reason other than the obvious (e.g., fixture name mismatch), inspect existing profile tests in `backend/tests/profile/` and align.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/profile/test_patch_manual_fields.py
git commit -m "test(profile): cover PATCH /profile/{id} manual-fields semantics"
```

---

## Task 5: Cover letter library view model + repo

**Files:**
- Modify: `backend/src/hiresense/applications/domain/aggregate.py`
- Modify: `backend/src/hiresense/applications/infrastructure/repository.py`

- [ ] **Step 1: Add `CoverLetterLibraryItem` view model**

In `backend/src/hiresense/applications/domain/aggregate.py`, append (end of file):

```python
class CoverLetterLibraryItem(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    job_title: str
    company: str
    body: str
    tone: str
    application_status: str
    created_at: datetime | None = None
```

- [ ] **Step 2: Add `list_all_cover_letters_with_apps` to `ApplicationRepository`**

In `backend/src/hiresense/applications/infrastructure/repository.py`, add an import for `TrackedApplication` at the top:

```python
from hiresense.tracking.domain.models import TrackedApplication
```

Then add this method to `ApplicationRepository`:

```python
    def list_all_cover_letters_with_apps(
        self,
    ) -> list[tuple[ApplicationCoverLetter, TrackedApplication]]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationCoverLetter, TrackedApplication)
                .join(TrackedApplication, ApplicationCoverLetter.application_id == TrackedApplication.id)
                .order_by(ApplicationCoverLetter.created_at.desc())
            )
            return [(letter, app) for letter, app in session.execute(stmt).all()]
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/applications/domain/aggregate.py backend/src/hiresense/applications/infrastructure/repository.py
git commit -m "feat(applications): cross-app cover letter library view + repo query"
```

---

## Task 6: Cover letter library — service + route + tests

**Files:**
- Modify: `backend/src/hiresense/applications/domain/application_service.py`
- Modify: `backend/src/hiresense/applications/api/routes.py`
- Create: `backend/tests/applications/test_cover_letter_library.py`

- [ ] **Step 1: Find the existing ApplicationService and its constructor pattern**

```bash
grep -n "class ApplicationService" backend/src/hiresense/applications/domain/application_service.py
```

- [ ] **Step 2: Add the service method**

In `backend/src/hiresense/applications/domain/application_service.py`, add to `ApplicationService` (mirror naming used by sibling methods):

```python
    def list_all_cover_letters(self) -> list[CoverLetterLibraryItem]:
        rows = self._repo.list_all_cover_letters_with_apps()
        return [
            CoverLetterLibraryItem(
                id=letter.id,
                application_id=letter.application_id,
                job_title=app.title,
                company=app.company,
                body=letter.body,
                tone=letter.tone,
                application_status=str(app.status),
                created_at=letter.created_at,
            )
            for letter, app in rows
        ]
```

Add `CoverLetterLibraryItem` to the imports at the top of the file:

```python
from hiresense.applications.domain.aggregate import (
    # ... existing imports ...
    CoverLetterLibraryItem,
)
```

- [ ] **Step 3: Add the GET route**

In `backend/src/hiresense/applications/api/routes.py`, find where `ApplicationService` is imported and ensure `CoverLetterLibraryItem` is imported alongside it. Then add a route (place it near `@router.get("", response_model=list[ApplicationListItemResponse])`):

```python
@router.get("/cover-letters", response_model=list[CoverLetterLibraryItem])
async def list_cover_letters_library(
    service: ApplicationService = Depends(get_application_service),
) -> list[CoverLetterLibraryItem]:
    return service.list_all_cover_letters()
```

**Important:** This route's path is `/cover-letters` under the `/applications` prefix. FastAPI route ordering matters — make sure this route is declared **before** any catch-all `/{application_id}` route (currently lines 86, 97, etc. in `routes.py`), otherwise `cover-letters` would be parsed as a UUID and 422. If `/{application_id}` is declared earlier, move the new route above it.

- [ ] **Step 4: Write tests**

Create `backend/tests/applications/test_cover_letter_library.py`:

```python
"""Tests for GET /applications/cover-letters — cross-app library."""
from __future__ import annotations


def test_empty_library_returns_empty_list(client) -> None:
    resp = client.get("/applications/cover-letters")
    assert resp.status_code == 200
    assert resp.json() == []


def test_library_returns_newest_first_with_app_info(client) -> None:
    # Create two applications + a cover letter on each
    app_a = client.post("/applications", json={"title": "Backend Engineer", "company": "Acme"}).json()
    app_b = client.post("/applications", json={"title": "Frontend Engineer", "company": "Globex"}).json()

    # Use the existing cover letter generator — needs the LLM, so for unit tests
    # we insert directly via the repo or use whatever the test pattern is in
    # backend/tests/applications/ (look for how cover letters are created in tests).
    # If there's no easy injection path, use the API endpoint with a mocked LLM
    # (check conftest for existing patterns).

    # Pseudocode — actual fixture wiring depends on what conftest exposes:
    _seed_cover_letter(app_a["id"], body="Hello Acme", tone="professional")
    _seed_cover_letter(app_b["id"], body="Hello Globex", tone="enthusiastic")

    resp = client.get("/applications/cover-letters")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    # Newest first
    assert items[0]["job_title"] == "Frontend Engineer"
    assert items[0]["company"] == "Globex"
    assert items[0]["body"] == "Hello Globex"
    assert items[1]["job_title"] == "Backend Engineer"


def test_deleting_app_removes_its_letters(client) -> None:
    app = client.post("/applications", json={"title": "X", "company": "Y"}).json()
    _seed_cover_letter(app["id"], body="hi", tone="professional")
    client.delete(f"/applications/{app['id']}")
    resp = client.get("/applications/cover-letters")
    assert all(item["application_id"] != app["id"] for item in resp.json())
```

The `_seed_cover_letter` helper must be replaced with the project's actual pattern for inserting cover letters in tests — inspect `backend/tests/applications/` for existing patterns. If there's no straightforward way, mock the LLM and call the real `POST /applications/{id}/cover-letter` endpoint.

- [ ] **Step 5: Run all backend tests**

```bash
cd backend && uv run pytest -v 2>&1 | tail -30
```

Expected: all green, including the new 3 + 5 tests from Task 4.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/applications/domain/application_service.py backend/src/hiresense/applications/api/routes.py backend/tests/applications/test_cover_letter_library.py
git commit -m "feat(applications): GET /cover-letters library endpoint + tests"
```

---

## Task 7: Frontend models + services

**Files:**
- Modify: `frontend/src/app/pages/profile/models/candidate-profile.model.ts`
- Create: `frontend/src/app/pages/applications/models/cover-letter-library-item.model.ts`
- Modify: `frontend/src/app/core/services/profile.service.ts`
- Modify: `frontend/src/app/core/services/applications.service.ts`

- [ ] **Step 1: Extend `CandidateProfile`**

In `frontend/src/app/pages/profile/models/candidate-profile.model.ts`, replace the interface with:

```typescript
import { CVSection } from './cv-section.model';

export interface CandidateProfile {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  location: string | null;
  sections: CVSection[];
  raw_tex: string;
  language: string;
  skills: string[];
  name_override?: string | null;
  location_override?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  portfolio_url?: string | null;
}
```

- [ ] **Step 2: Create the library-item interface**

Create `frontend/src/app/pages/applications/models/cover-letter-library-item.model.ts`:

```typescript
export interface CoverLetterLibraryItem {
  id: string;
  application_id: string;
  job_title: string;
  company: string;
  body: string;
  tone: string;
  application_status: string;
  created_at: string;
}
```

- [ ] **Step 3: Add `updateProfile` to `ProfileService`**

In `frontend/src/app/core/services/profile.service.ts`, add a method (after the existing `uploadFile` or wherever fits the file's order):

```typescript
  updateProfile(id: string, patch: Partial<{
    name_override: string | null;
    location_override: string | null;
    linkedin_url: string | null;
    github_url: string | null;
    portfolio_url: string | null;
  }>): Observable<CandidateProfile> {
    return this.http.patch<CandidateProfile>(`${this.baseUrl}/${id}`, patch).pipe(
      tap((updated) => {
        // Refresh the local signal so the UI updates.
        const current = this.profile();
        if (current && current.id === updated.id) {
          this.profile.set(updated);
        }
      }),
    );
  }
```

Verify `tap` is imported from `rxjs` at the top — if not, add it. `Observable` likely already imported.

- [ ] **Step 4: Add `listAllCoverLetters` to `ApplicationsService`**

In `frontend/src/app/core/services/applications.service.ts`, add the import:

```typescript
import { CoverLetterLibraryItem } from '../../pages/applications/models/cover-letter-library-item.model';
```

And the method (place it with the other GET methods):

```typescript
  listAllCoverLetters(): Observable<CoverLetterLibraryItem[]> {
    return this.http.get<CoverLetterLibraryItem[]>(`${this.baseUrl}/cover-letters`);
  }
```

- [ ] **Step 5: Frontend build check**

```bash
cd frontend && npx ng build --configuration=development 2>&1 | tail -5
```

Expected: clean build (warnings about unused imports are OK at this stage — they'll be used in Task 8/9).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/pages/profile/models/candidate-profile.model.ts frontend/src/app/pages/applications/models/cover-letter-library-item.model.ts frontend/src/app/core/services/profile.service.ts frontend/src/app/core/services/applications.service.ts
git commit -m "feat(frontend): models + services for profile patch and cover letter library"
```

---

## Task 8: Personal details — Edit mode

**Files:**
- Modify: `frontend/src/app/pages/profile/profile.component.ts`
- Modify: `frontend/src/app/pages/profile/profile.component.html`
- Modify: `frontend/src/app/pages/profile/profile.component.scss`

- [ ] **Step 1: Component state + handlers**

In `frontend/src/app/pages/profile/profile.component.ts`, add these signals/methods (next to the existing edit-related state in the class body):

```typescript
  // Personal details edit mode
  editingPersonal = signal(false);
  editName = signal('');
  editLocation = signal('');
  editLinkedin = signal('');
  editGithub = signal('');
  editPortfolio = signal('');
  savingPersonal = signal(false);
  personalError = signal('');

  effectiveName = computed(() => {
    const p = this.profile();
    return p ? (p.name_override || p.name || '') : '';
  });

  effectiveLocation = computed(() => {
    const p = this.profile();
    return p ? (p.location_override || p.location || '') : '';
  });

  startEditPersonal(): void {
    const p = this.profile();
    if (!p) return;
    this.editName.set(p.name_override ?? '');
    this.editLocation.set(p.location_override ?? '');
    this.editLinkedin.set(p.linkedin_url ?? '');
    this.editGithub.set(p.github_url ?? '');
    this.editPortfolio.set(p.portfolio_url ?? '');
    this.personalError.set('');
    this.editingPersonal.set(true);
  }

  cancelEditPersonal(): void {
    this.editingPersonal.set(false);
    this.personalError.set('');
  }

  savePersonal(): void {
    const p = this.profile();
    if (!p) return;
    this.savingPersonal.set(true);
    this.personalError.set('');
    const patch = {
      name_override: this.editName().trim() || null,
      location_override: this.editLocation().trim() || null,
      linkedin_url: this.editLinkedin().trim() || null,
      github_url: this.editGithub().trim() || null,
      portfolio_url: this.editPortfolio().trim() || null,
    };
    this.profileService.updateProfile(p.id, patch).subscribe({
      next: () => {
        this.savingPersonal.set(false);
        this.editingPersonal.set(false);
      },
      error: (err) => {
        this.personalError.set(err.error?.detail || 'Failed to update profile');
        this.savingPersonal.set(false);
      },
    });
  }

  urlLabel(url: string): string {
    try {
      const u = new URL(url);
      return u.host + u.pathname.replace(/\/$/, '');
    } catch {
      return url;
    }
  }
```

- [ ] **Step 2: Personal details template — read + edit modes**

In `frontend/src/app/pages/profile/profile.component.html`, find the Personal details panel (the `@if (pageTab() === 'personal')` block). Replace its contents (everything between `<section class="tab-panel">` and `</section>`) with:

```html
    @if (profile(); as p) {
      @if (!editingPersonal()) {
        <div class="details-card">
          <div class="details-header">
            <h3>Your details</h3>
            <button type="button" class="btn-secondary btn-sm" (click)="startEditPersonal()">Edit</button>
          </div>
          <div class="details-grid">
            <div class="details-item">
              <span class="details-label">Name</span>
              <span class="details-value">{{ effectiveName() || '—' }}</span>
            </div>
            <div class="details-item">
              <span class="details-label">Email</span>
              <span class="details-value">{{ p.email || '—' }}</span>
            </div>
            <div class="details-item">
              <span class="details-label">Phone</span>
              <span class="details-value">{{ p.phone || '—' }}</span>
            </div>
            <div class="details-item">
              <span class="details-label">Location</span>
              <span class="details-value">{{ effectiveLocation() || '—' }}</span>
            </div>
            <div class="details-item">
              <span class="details-label">Primary language</span>
              <span class="details-value">{{ p.language === 'es' ? 'Espanol' : 'English' }}</span>
            </div>
            @if (p.linkedin_url) {
              <div class="details-item">
                <span class="details-label">LinkedIn</span>
                <a class="details-link" [href]="p.linkedin_url" target="_blank" rel="noopener">{{ urlLabel(p.linkedin_url) }}</a>
              </div>
            }
            @if (p.github_url) {
              <div class="details-item">
                <span class="details-label">GitHub</span>
                <a class="details-link" [href]="p.github_url" target="_blank" rel="noopener">{{ urlLabel(p.github_url) }}</a>
              </div>
            }
            @if (p.portfolio_url) {
              <div class="details-item">
                <span class="details-label">Portfolio</span>
                <a class="details-link" [href]="p.portfolio_url" target="_blank" rel="noopener">{{ urlLabel(p.portfolio_url) }}</a>
              </div>
            }
          </div>
          <p class="details-source-note">
            Name and location fall back to what was parsed from your CV unless you've set an override.
          </p>
        </div>
      } @else {
        <form class="details-card edit-form" (submit)="$event.preventDefault(); savePersonal()">
          <div class="details-header">
            <h3>Edit your details</h3>
          </div>
          <div class="edit-grid">
            <label class="edit-field">
              <span class="edit-label">Name (override)</span>
              <input type="text" [ngModel]="editName()" (ngModelChange)="editName.set($event)" name="name" [placeholder]="profile()!.name || 'Your name'" />
            </label>
            <label class="edit-field">
              <span class="edit-label">Location (override)</span>
              <input type="text" [ngModel]="editLocation()" (ngModelChange)="editLocation.set($event)" name="location" [placeholder]="profile()!.location || 'City, Country'" />
            </label>
            <label class="edit-field">
              <span class="edit-label">LinkedIn</span>
              <input type="url" [ngModel]="editLinkedin()" (ngModelChange)="editLinkedin.set($event)" name="linkedin" placeholder="https://linkedin.com/in/you" />
            </label>
            <label class="edit-field">
              <span class="edit-label">GitHub</span>
              <input type="url" [ngModel]="editGithub()" (ngModelChange)="editGithub.set($event)" name="github" placeholder="https://github.com/you" />
            </label>
            <label class="edit-field edit-field-wide">
              <span class="edit-label">Portfolio</span>
              <input type="url" [ngModel]="editPortfolio()" (ngModelChange)="editPortfolio.set($event)" name="portfolio" placeholder="https://your-site.com" />
            </label>
          </div>
          @if (personalError()) {
            <div class="alert alert-error">{{ personalError() }}</div>
          }
          <div class="edit-actions">
            <button type="button" class="btn-secondary" (click)="cancelEditPersonal()">Cancel</button>
            <button type="submit" class="btn-primary" [disabled]="savingPersonal()">
              @if (savingPersonal()) { Saving... } @else { Save }
            </button>
          </div>
        </form>
      }
    } @else {
      <div class="empty-state">
        <p class="empty-state-title">No profile yet</p>
        <p class="empty-state-hint">
          Upload a CV in the <button type="button" class="link-button" (click)="pageTab.set('cv')">CV tab</button> to see your parsed details here.
        </p>
      </div>
    }
```

Also: **remove the "Coming soon — Manual fields" card** that was in the Personal details panel (it has been replaced by the actual feature).

Also: update the avatar's initial in the CV tab — find `{{ profile()!.name.charAt(0).toUpperCase() }}` and replace with `{{ effectiveName().charAt(0).toUpperCase() }}`. Same for the location display `{{ profile()!.location }}` → `{{ effectiveLocation() }}` (and update the `@if` guard to `@if (effectiveLocation())`).

- [ ] **Step 3: Styles for edit form + new bits**

Append to `frontend/src/app/pages/profile/profile.component.scss`:

```scss
// --- Personal details: header + edit form ---
.details-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;

  h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: $text-dark;
    text-transform: none;
    letter-spacing: 0;
  }
}

.details-link {
  font-size: 0.9rem;
  color: $primary;
  text-decoration: none;
  font-weight: 500;
  word-break: break-all;

  &:hover { text-decoration: underline; }
}

.edit-form { padding-top: 1.25rem; }

.edit-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem 1.5rem;
  margin-bottom: 1.25rem;
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;

  &.edit-field-wide { grid-column: 1 / -1; }

  input {
    padding: 0.55rem 0.75rem;
    border: 1px solid $border;
    border-radius: 6px;
    font-size: 0.9rem;
    color: $text-dark;
    background: $surface;
    font-family: inherit;
    transition: border-color $transition, box-shadow $transition;

    &::placeholder { color: #c0c5ce; }

    &:focus {
      outline: none;
      border-color: $primary;
      box-shadow: 0 0 0 3px rgba($primary, 0.1);
    }
  }
}

.edit-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: $text-mid;
  letter-spacing: 0.02em;
}

.edit-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  padding-top: 1rem;
  border-top: 1px solid $border;
}
```

- [ ] **Step 4: Build + verify**

```bash
cd frontend && npx ng build 2>&1 | tail -5
```

Expected: clean. (You should also remove the now-orphaned "Coming soon — Manual fields" stub from the HTML if you haven't already.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/profile/profile.component.ts frontend/src/app/pages/profile/profile.component.html frontend/src/app/pages/profile/profile.component.scss
git commit -m "feat(profile): Personal details edit mode for manual override fields

Users can now override the CV-parsed name and location, and add
LinkedIn / GitHub / portfolio URLs. Read view shows links when set
and falls back to parsed values via effectiveName/effectiveLocation."
```

---

## Task 9: Cover letters — Library list

**Files:**
- Modify: `frontend/src/app/pages/profile/profile.component.ts`
- Modify: `frontend/src/app/pages/profile/profile.component.html`
- Modify: `frontend/src/app/pages/profile/profile.component.scss`

- [ ] **Step 1: Component state + loaders**

In `frontend/src/app/pages/profile/profile.component.ts`, add the imports at the top:

```typescript
import { ApplicationsService } from '../../core/services/applications.service';
import { CoverLetterLibraryItem } from '../applications/models/cover-letter-library-item.model';
```

Add to the constructor area (sibling to `profileService`):

```typescript
  private applicationsService = inject(ApplicationsService);
```

Add signals + methods (next to the other tab state):

```typescript
  coverLetters = signal<CoverLetterLibraryItem[] | null>(null);
  coverLettersLoading = signal(false);
  coverLettersError = signal('');
  copiedId = signal<string | null>(null);

  loadCoverLetters(): void {
    if (this.coverLetters() !== null || this.coverLettersLoading()) return;
    this.coverLettersLoading.set(true);
    this.coverLettersError.set('');
    this.applicationsService.listAllCoverLetters().subscribe({
      next: (items) => {
        this.coverLetters.set(items);
        this.coverLettersLoading.set(false);
      },
      error: (err) => {
        this.coverLettersError.set(err.error?.detail || 'Failed to load cover letters');
        this.coverLettersLoading.set(false);
      },
    });
  }

  copyBody(item: CoverLetterLibraryItem): void {
    navigator.clipboard.writeText(item.body).then(() => {
      this.copiedId.set(item.id);
      setTimeout(() => {
        if (this.copiedId() === item.id) this.copiedId.set(null);
      }, 1500);
    });
  }

  relativeTime(iso: string): string {
    const then = new Date(iso).getTime();
    if (isNaN(then)) return '';
    const diff = Date.now() - then;
    const minute = 60_000, hour = 60 * minute, day = 24 * hour;
    if (diff < hour) return `${Math.max(1, Math.round(diff / minute))}m ago`;
    if (diff < day) return `${Math.round(diff / hour)}h ago`;
    if (diff < 30 * day) return `${Math.round(diff / day)}d ago`;
    if (diff < 365 * day) return `${Math.round(diff / (30 * day))}mo ago`;
    return `${Math.round(diff / (365 * day))}y ago`;
  }
```

Trigger the load when the cover-letters tab becomes active. Modify `pageTab` to track activation — simplest is a small wrapper method:

```typescript
  selectTab(tab: ProfilePageTab): void {
    this.pageTab.set(tab);
    if (tab === 'cover-letters') this.loadCoverLetters();
  }
```

In the template (Task 4 from Phase 1), the three page tabs use `(click)="pageTab.set(...)"`. **Change all three** to `(click)="selectTab(...)"` so the library auto-loads on tab activation.

- [ ] **Step 2: Cover letters template — replace stubs with Library**

In `frontend/src/app/pages/profile/profile.component.html`, find the Cover letters panel (`@if (pageTab() === 'cover-letters')`). Replace its contents (between `<section class="tab-panel">` and `</section>`) with:

```html
    <div class="per-job-card">
      <div class="per-job-icon" aria-hidden="true">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
          <polyline points="22,6 12,13 2,6"/>
        </svg>
      </div>
      <div class="per-job-body">
        <h3>Generate a new one</h3>
        <p>
          Cover letters are tailored to each specific job in the <strong>Applications</strong> tab.
          Open any application and use the <em>Apply</em> tab.
        </p>
        <a routerLink="/dashboard/applications" class="btn-primary per-job-cta">
          Go to Applications
        </a>
      </div>
    </div>

    <div class="library-section">
      <h3 class="library-heading">Library</h3>

      @if (coverLettersLoading()) {
        <div class="library-loading">Loading…</div>
      } @else if (coverLettersError()) {
        <div class="alert alert-error">{{ coverLettersError() }}</div>
      } @else if (coverLetters() === null || coverLetters()!.length === 0) {
        <div class="library-empty">
          <p>You haven't generated any cover letters yet.</p>
          <p class="library-empty-hint">Open an application and use the Apply tab to create your first one.</p>
        </div>
      } @else {
        <div class="library-list">
          @for (item of coverLetters(); track item.id) {
            <div class="library-item">
              <div class="library-item-header">
                <div class="library-item-titles">
                  <h4>{{ item.job_title }}</h4>
                  <span class="library-item-company">{{ item.company }}</span>
                </div>
                <div class="library-item-badges">
                  <span class="badge tone-badge">{{ item.tone }}</span>
                  <span class="badge status-badge status-{{ item.application_status }}">{{ item.application_status }}</span>
                  <span class="library-item-time">{{ relativeTime(item.created_at) }}</span>
                </div>
              </div>
              <p class="library-item-body">{{ item.body }}</p>
              <div class="library-item-actions">
                <button type="button" class="btn-secondary btn-sm" (click)="copyBody(item)">
                  @if (copiedId() === item.id) { ✓ Copied } @else { Copy body }
                </button>
                <a class="btn-secondary btn-sm" [routerLink]="['/dashboard/applications', item.application_id]">
                  Open application
                </a>
              </div>
            </div>
          }
        </div>
      }
    </div>

    <div class="coming-soon-card">
      <div class="coming-soon-badge">Coming soon</div>
      <h3>Templates</h3>
      <p>Reusable cover letter templates you can pick from when applying — set the tone, opening, and signature once.</p>
    </div>
```

(The Library section replaces the Phase 1 "Library — Coming soon" stub. The "Templates" stub stays for Phase 3.)

- [ ] **Step 3: Library styles**

Append to `frontend/src/app/pages/profile/profile.component.scss`:

```scss
// --- Cover letters: library list ---
.library-section { margin-bottom: 1.25rem; }

.library-heading {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
  color: $text-light;
  margin: 0 0 0.75rem;
}

.library-loading {
  padding: 2rem;
  text-align: center;
  color: $text-light;
  background: $surface;
  border-radius: $radius;
  box-shadow: $shadow-sm;
}

.library-empty {
  padding: 2rem 1.5rem;
  text-align: center;
  background: $surface;
  border-radius: $radius;
  box-shadow: $shadow-sm;

  p {
    margin: 0;
    color: $text-mid;
    font-size: 0.9rem;
  }

  .library-empty-hint {
    color: $text-light;
    font-size: 0.85rem;
    margin-top: 0.4rem;
  }
}

.library-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.library-item {
  background: $surface;
  border-radius: $radius;
  box-shadow: $shadow-sm;
  padding: 1.15rem 1.35rem;
}

.library-item-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 0.65rem;
}

.library-item-titles {
  min-width: 0;

  h4 {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: $text-dark;
  }
}

.library-item-company {
  display: block;
  font-size: 0.82rem;
  color: $text-light;
  margin-top: 0.1rem;
}

.library-item-badges {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.library-item-time {
  font-size: 0.75rem;
  color: $text-light;
}

.badge {
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 0.18rem 0.5rem;
  border-radius: 4px;
}

.tone-badge {
  background: $primary-light;
  color: $primary-dark;
}

.status-badge {
  background: #f1f5f9;
  color: #475569;
}

.status-badge.status-applied {
  background: #dcfce7;
  color: #166534;
}

.status-badge.status-interviewing {
  background: #fef3c7;
  color: #92400e;
}

.status-badge.status-offered {
  background: #dbeafe;
  color: #1e40af;
}

.status-badge.status-rejected {
  background: #fee2e2;
  color: #991b1b;
}

.library-item-body {
  margin: 0 0 0.85rem;
  font-size: 0.85rem;
  line-height: 1.55;
  color: $text-mid;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-wrap;
}

.library-item-actions {
  display: flex;
  gap: 0.5rem;
}
```

- [ ] **Step 4: Build + verify**

```bash
cd frontend && npx ng build 2>&1 | tail -8
```

Expected: clean (or only the well-known component-style budget warning that we already raised in Phase 1).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/profile/profile.component.ts frontend/src/app/pages/profile/profile.component.html frontend/src/app/pages/profile/profile.component.scss
git commit -m "feat(profile): cover letter Library list on Cover letters tab

Lazy-loads on first tab activation. Each card shows job + company,
tone + application-status badges, relative time, truncated body
preview, and copy-body / open-application actions. Replaces the
Phase 1 'Library — Coming soon' stub."
```

---

## Task 10: Final verification + PR

**Files:** None modified.

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && uv run pytest 2>&1 | tail -10
```

Expected: all green.

- [ ] **Step 2: Run frontend production build**

```bash
cd frontend && npx ng build 2>&1 | tail -5
```

Expected: bundle generation complete, no errors.

- [ ] **Step 3: Push branch + open PR2**

```bash
git push -u origin feat/profile-personal-and-letter-library
```

Then `gh pr create --base feat/profile-hub-and-sidebar-polish --head feat/profile-personal-and-letter-library --title "feat(profile): personal details edit + cover letter library" --body "..."` — base must be the Phase 1 branch since this is stacked.

(If Phase 1 has merged to main by this point, base on main instead.)

---

## Self-review

**Spec coverage:**
- Migration 007 (5 nullable columns) → Task 1 ✓
- SQLAlchemy + Pydantic `CandidateProfile` extension → Task 2 ✓
- `ProfileRepository.update_manual_fields` → Task 2 ✓
- Service `update_profile` + PATCH route with URL validation → Task 3 ✓
- 5 PATCH tests (each field, omitted preserved, null clears, bad URL, 404) → Task 4 ✓
- `CoverLetterLibraryItem` view + cross-app repo query → Task 5 ✓
- Service `list_all_cover_letters` + GET route + 3 tests → Task 6 ✓
- Frontend models + services → Task 7 ✓
- Personal details Edit mode + read view with URLs + effectiveName/Location → Task 8 ✓
- Cover letters Library list with badges, copy, open application → Task 9 ✓
- Final verification + PR ship → Task 10 ✓

**Type consistency:**
- 5 manual-field names identical across migration, ORM, pydantic, frontend interface, PATCH request, edit signals ✓
- `CoverLetterLibraryItem` identical between backend pydantic and frontend interface ✓
- Route paths exact (`/profile/{profile_id}`, `/applications/cover-letters`) ✓
- `pageTab.set` callers replaced with `selectTab` in Task 9 Step 1 — this needs to also update the 3 occurrences in the page-tab buttons (Task 4 of Phase 1 plan) ✓ (covered in Step 1 instructions)

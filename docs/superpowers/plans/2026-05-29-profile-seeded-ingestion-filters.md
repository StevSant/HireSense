# Profile-seeded Ingestion Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On first load of the ingestion page, pre-select the seniority band and max-years cap inferred from the candidate's CV, while keeping every control manually overridable.

**Architecture:** A pure backend function turns the candidate's CV summary into a seniority band (inferred level ±1) and a max-years cap (CV years + a configurable buffer). A new `GET /ingestion/profile-defaults` endpoint exposes it. The Angular `JobFiltersComponent` fetches it once on init (guarded by a `localStorage` marker) and seeds the filter chips/inputs; the user can override freely thereafter.

**Tech Stack:** Python / FastAPI / Pydantic / pytest (backend); Angular standalone components / RxJS (frontend).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `backend/src/hiresense/config.py` | Add `ingestion_seniority_years_buffer` setting | Modify |
| `backend/.env.example` | Document the new setting | Modify |
| `backend/src/hiresense/ingestion/domain/profile_filter_defaults.py` | Band/years math + `ProfileFilterDefaults` DTO (co-located, mirroring `job_filter.py`) | Create |
| `backend/src/hiresense/ingestion/domain/__init__.py` | Re-export new symbols | Modify |
| `backend/src/hiresense/ingestion/api/routes.py` | New `GET /ingestion/profile-defaults` route | Modify |
| `backend/tests/unit/ingestion/test_profile_filter_defaults.py` | Unit tests for the math | Create |
| `backend/tests/unit/ingestion/test_routes.py` | Endpoint test | Modify |
| `frontend/src/app/core/services/ingestion.service.ts` | `getProfileFilterDefaults()` + `ProfileFilterDefaults` interface | Modify |
| `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.ts` | Seed-once-on-init logic | Modify |

**Convention note:** `profile_filter_defaults.py` co-locates the DTO and the function in one module, following the established local pattern of `job_filter.py` (which co-locates `JobQueryParams`, `PaginatedResult`, and `filter_and_paginate`). This is the prevailing pattern in this exact domain folder.

---

## Task 1: Add the configurable years buffer

**Files:**
- Modify: `backend/src/hiresense/config.py:104` (after `ingestion_job_retention_days`)
- Modify: `backend/.env.example:82` (after `INGESTION_MIN_MATCH_SCORE`)

- [ ] **Step 1: Add the setting to `config.py`**

Insert after the `ingestion_job_retention_days` block (currently ending at line 104):

```python
    # Buffer added to the candidate's CV-stated years of experience when
    # seeding the ingestion max-years filter. e.g. 3 CV years + buffer 2 →
    # the list pre-filters to jobs asking <= 5 years, so roles asking
    # slightly more than the exact experience still surface. User-overridable
    # in the filter UI.
    ingestion_seniority_years_buffer: int = 2
```

- [ ] **Step 2: Document it in `.env.example`**

Insert after the `INGESTION_MIN_MATCH_SCORE=0.0` line (line 82):

```bash
# Buffer added to CV-stated years when seeding the ingestion max-years
# filter (CV years + buffer). Default 2.
INGESTION_SENIORITY_YEARS_BUFFER=2
```

- [ ] **Step 3: Verify the setting loads**

Run: `cd backend && uv run python -c "from hiresense.config import Settings; print('ok')"`
Expected: prints `ok` with no import error.

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example
git commit -m "feat(ingestion): add configurable seniority years buffer setting"
```

---

## Task 2: Band + years math (pure function)

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/profile_filter_defaults.py`
- Test: `backend/tests/unit/ingestion/test_profile_filter_defaults.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/ingestion/test_profile_filter_defaults.py`:

```python
from hiresense.ingestion.domain.profile_filter_defaults import (
    ProfileFilterDefaults,
    compute_profile_filter_defaults,
)
from hiresense.ingestion.domain.seniority import SeniorityLevel


def test_mid_expands_to_band_of_three():
    # CV-text inference only reaches MID via the years heuristic (2-4 yrs),
    # never via a "mid-level" keyword (the body rules match only
    # intern/junior/senior). 3 years → MID.
    result = compute_profile_filter_defaults(
        "Engineer with 3 years of experience", years_buffer=2
    )
    assert result.seniority == [
        SeniorityLevel.JUNIOR,
        SeniorityLevel.MID,
        SeniorityLevel.SENIOR,
    ]


def test_intern_clamps_at_low_end():
    result = compute_profile_filter_defaults("Software Intern", years_buffer=2)
    assert result.seniority == [SeniorityLevel.INTERN, SeniorityLevel.JUNIOR]


def test_lead_clamps_at_high_end():
    # LEAD is only reachable via the years heuristic (> 7 yrs); "tech lead" as
    # a keyword is not matched by the body-only rules. 10 years → LEAD.
    result = compute_profile_filter_defaults(
        "Architect with 10+ years of experience", years_buffer=2
    )
    assert result.seniority == [SeniorityLevel.SENIOR, SeniorityLevel.LEAD]


def test_unknown_seeds_empty_band():
    result = compute_profile_filter_defaults(
        "Passionate builder who loves shipping", years_buffer=2
    )
    assert result.seniority == []


def test_years_found_gets_buffer_added():
    # "5+ years of experience" → senior level; years 5 + buffer 2 = 7.
    result = compute_profile_filter_defaults(
        "Backend engineer with 5+ years of experience", years_buffer=2
    )
    assert result.max_years_experience == 7


def test_years_absent_is_none():
    result = compute_profile_filter_defaults("Senior software engineer", years_buffer=2)
    assert result.max_years_experience is None


def test_buffer_is_applied_from_argument():
    result = compute_profile_filter_defaults(
        "Engineer with 3+ years experience", years_buffer=5
    )
    assert result.max_years_experience == 8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_profile_filter_defaults.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hiresense.ingestion.domain.profile_filter_defaults'`.

- [ ] **Step 3: Write the implementation**

Create `backend/src/hiresense/ingestion/domain/profile_filter_defaults.py`:

```python
from __future__ import annotations

from pydantic import BaseModel

from hiresense.ingestion.domain.candidate_level import infer_candidate_level
from hiresense.ingestion.domain.seniority import SeniorityLevel, extract_min_years

# Ordered ladder used for the ±1 band. UNKNOWN is intentionally excluded:
# an unknown candidate level seeds an empty band (show all levels).
_LADDER: tuple[SeniorityLevel, ...] = (
    SeniorityLevel.INTERN,
    SeniorityLevel.JUNIOR,
    SeniorityLevel.MID,
    SeniorityLevel.SENIOR,
    SeniorityLevel.LEAD,
)


class ProfileFilterDefaults(BaseModel):
    """Filter values seeded from the candidate's CV for the ingestion page."""

    seniority: list[SeniorityLevel]
    max_years_experience: int | None


def _band_around(level: SeniorityLevel) -> list[SeniorityLevel]:
    """Return the inferred level plus one neighbour on each side, clamped.

    UNKNOWN (or any level not on the ladder) yields an empty band, which the
    UI reads as "no seniority pre-selected — show every level".
    """
    if level not in _LADDER:
        return []
    i = _LADDER.index(level)
    start = max(0, i - 1)
    end = i + 2  # slice end is exclusive, so i+1 is included
    return list(_LADDER[start:end])


def compute_profile_filter_defaults(
    summary: str, years_buffer: int
) -> ProfileFilterDefaults:
    """Derive seeded seniority band + max-years cap from CV summary text.

    - Seniority: inferred candidate level ±1 (empty when UNKNOWN).
    - Max years: smallest CV-stated years + ``years_buffer``; None when the CV
      states no years.
    """
    level = infer_candidate_level(summary)
    band = _band_around(level)

    cv_years = extract_min_years(summary)
    max_years = cv_years + years_buffer if cv_years is not None else None

    return ProfileFilterDefaults(seniority=band, max_years_experience=max_years)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_profile_filter_defaults.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Re-export from the package `__init__.py`**

Modify `backend/src/hiresense/ingestion/domain/__init__.py` — add the import and `__all__` entries (keep the existing alphabetised style):

```python
from hiresense.ingestion.domain.job_filter import JobQueryParams, PaginatedResult, filter_and_paginate
from hiresense.ingestion.domain.portal_config import load_portals_config
from hiresense.ingestion.domain.portal_scanner import PortalScanner
from hiresense.ingestion.domain.profile_filter_defaults import (
    ProfileFilterDefaults,
    compute_profile_filter_defaults,
)
from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict
from hiresense.ingestion.domain.services import IngestionOrchestrator

__all__ = [
    "IngestionOrchestrator",
    "JobQueryParams",
    "PaginatedResult",
    "PortalScanner",
    "ProfileFilterDefaults",
    "QuickMatchResult",
    "QuickMatchVerdict",
    "compute_profile_filter_defaults",
    "filter_and_paginate",
    "load_portals_config",
]
```

- [ ] **Step 6: Verify the re-export works**

Run: `cd backend && uv run python -c "from hiresense.ingestion.domain import compute_profile_filter_defaults, ProfileFilterDefaults; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/profile_filter_defaults.py backend/src/hiresense/ingestion/domain/__init__.py backend/tests/unit/ingestion/test_profile_filter_defaults.py
git commit -m "feat(ingestion): compute profile-seeded filter defaults"
```

---

## Task 3: Expose the `GET /ingestion/profile-defaults` endpoint

**Files:**
- Modify: `backend/src/hiresense/ingestion/api/routes.py` (imports + new route)
- Test: `backend/tests/unit/ingestion/test_routes.py`

- [ ] **Step 1: Write the failing endpoint tests**

Append to `backend/tests/unit/ingestion/test_routes.py`. The default `FakeProfileService` returns `[]` (no profile → empty band, null years). Add a second fake for the populated case:

```python
class FakeProfileWithCv:
    """A profile whose section text reads as a senior, 5-years candidate."""

    def __init__(self):
        self.id = "p1"
        self.skills = ["python"]
        self.sections = [
            type("S", (), {"content": "Senior engineer with 5+ years of experience"})()
        ]


class FakeProfileServiceWithCv:
    async def list_profiles(self):
        return [FakeProfileWithCv()]


@pytest.mark.asyncio
async def test_profile_defaults_empty_when_no_profile() -> None:
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/profile-defaults")
    assert resp.status_code == 200
    data = resp.json()
    assert data["seniority"] == []
    assert data["max_years_experience"] is None


@pytest.mark.asyncio
async def test_profile_defaults_seeds_band_and_years() -> None:
    app, _, _ = _make_app()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileServiceWithCv()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/profile-defaults")
    assert resp.status_code == 200
    data = resp.json()
    # "Senior ... 5+ years" → senior band (mid, senior, lead) and 5 + default buffer 2 = 7.
    assert data["seniority"] == ["mid", "senior", "lead"]
    assert data["max_years_experience"] == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_routes.py -k profile_defaults -v`
Expected: FAIL with `404` responses (route not yet defined).

- [ ] **Step 3: Add imports to `routes.py`**

In `backend/src/hiresense/ingestion/api/routes.py`, extend the existing job_filter import line (line 18) to add a sibling import below it:

```python
from hiresense.ingestion.domain.job_filter import JobQueryParams, PaginatedResult, filter_and_paginate
from hiresense.ingestion.domain.profile_filter_defaults import (
    ProfileFilterDefaults,
    compute_profile_filter_defaults,
)
```

- [ ] **Step 4: Add the route**

In `backend/src/hiresense/ingestion/api/routes.py`, add this route immediately after the `list_jobs` function (after its `return result` at line 240, before `analyze_job`). It reads the buffer from `app.state.settings`, falling back to `2` when settings is absent (bare test app), mirroring how `list_jobs` handles `min_score`:

```python
@router.get("/profile-defaults", response_model=ProfileFilterDefaults)
async def profile_defaults(
    request: Request,
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileFilterDefaults:
    """Seed values for the ingestion seniority/years filters, derived from the
    candidate's CV. Empty band + null years when no profile/signal exists."""
    _, candidate_summary = await _gather_profile(profile_service)
    settings = getattr(request.app.state, "settings", None)
    years_buffer = settings.ingestion_seniority_years_buffer if settings is not None else 2
    return compute_profile_filter_defaults(candidate_summary, years_buffer)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_routes.py -k profile_defaults -v`
Expected: both `profile_defaults` tests PASS.

- [ ] **Step 6: Run the full ingestion test module (no regressions)**

Run: `cd backend && uv run pytest tests/unit/ingestion/ -q`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/ingestion/api/routes.py backend/tests/unit/ingestion/test_routes.py
git commit -m "feat(ingestion): add profile-defaults endpoint"
```

---

## Task 4: Frontend service method

**Files:**
- Modify: `frontend/src/app/core/services/ingestion.service.ts`

- [ ] **Step 1: Add the response interface**

In `frontend/src/app/core/services/ingestion.service.ts`, add after the `JobFilters` interface (after line 27):

```typescript
export interface ProfileFilterDefaults {
  seniority: SeniorityLevel[];
  max_years_experience: number | null;
}
```

- [ ] **Step 2: Add the service method**

In the same file, add this method inside `IngestionService` (e.g. after `loadPortals`, before `scanPortals`):

```typescript
  getProfileFilterDefaults(): Observable<ProfileFilterDefaults> {
    return this.http.get<ProfileFilterDefaults>(
      `${environment.apiUrl}/ingestion/profile-defaults`,
    );
  }
```

- [ ] **Step 3: Verify the frontend still type-checks/builds**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/core/services/ingestion.service.ts
git commit -m "feat(ingestion): add getProfileFilterDefaults service method"
```

---

## Task 5: Seed filters once on load

**Files:**
- Modify: `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.ts`

- [ ] **Step 1: Add imports and the marker constant**

In `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.ts`, update the top imports and storage-key constants. Replace the existing import block (lines 1-6) with:

```typescript
import { Component, OnInit, inject, input, output } from '@angular/core';
import { IngestionService, JobFilters, SeniorityLevel } from '../../../../core/services/ingestion.service';
import { detectUserLocation } from '../../../../core/utils/detect-user-location';

const LS_USER_LOCATION = 'hiresense.user_location';
const LS_STRICT_LOCATION = 'hiresense.strict_location_match';
const LS_FILTERS_SEEDED = 'hiresense.filters_seeded';
```

> Note: `JobFilters` and `SeniorityLevel` were previously imported from `ingestion.service`; this keeps that and adds `IngestionService`.

- [ ] **Step 2: Inject the service**

Add the injected service as a class field (just below the `filtersChange` output, before `debounceTimer`):

```typescript
  private readonly ingestion = inject(IngestionService);
```

- [ ] **Step 3: Seed once in `ngOnInit`**

Replace the existing `ngOnInit` body so it keeps the location/strict seeding AND adds the one-time profile seeding. The new method:

```typescript
  ngOnInit(): void {
    let storedLocation = localStorage.getItem(LS_USER_LOCATION);
    if (!storedLocation) {
      const detected = detectUserLocation();
      if (detected) {
        storedLocation = detected;
        localStorage.setItem(LS_USER_LOCATION, detected);
      }
    }
    const storedStrict = localStorage.getItem(LS_STRICT_LOCATION) === 'true';
    if (storedLocation || storedStrict) {
      this.emitFilters({
        user_location: storedLocation || undefined,
        strict_location: storedStrict || undefined,
      });
    }

    // One-time seeding of seniority/years from the candidate profile. The
    // marker makes this fire only on the first ever visit; afterwards the
    // user's manual choices (including an intentional "clear all") are never
    // re-overridden.
    if (localStorage.getItem(LS_FILTERS_SEEDED) !== 'true') {
      this.ingestion.getProfileFilterDefaults().subscribe((defaults) => {
        localStorage.setItem(LS_FILTERS_SEEDED, 'true');
        const seeded: Partial<JobFilters> = {};
        if (defaults.seniority.length) {
          seeded.seniority = defaults.seniority;
        }
        if (defaults.max_years_experience !== null) {
          seeded.max_years_experience = defaults.max_years_experience;
        }
        if (seeded.seniority || seeded.max_years_experience !== undefined) {
          this.emitFilters(seeded);
        }
      });
    }
  }
```

- [ ] **Step 4: Verify `clearAll` does NOT clear the marker**

Confirm the existing `clearAll()` method is unchanged — it must not touch `LS_FILTERS_SEEDED`. (No edit needed; this step is a read-check of the current `clearAll`, which only reads `LS_USER_LOCATION` / `LS_STRICT_LOCATION`.)

- [ ] **Step 5: Verify the frontend builds**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors.

- [ ] **Step 6: Manual smoke test**

1. Start backend + frontend (`docker-compose up` or the project's usual dev command).
2. In the browser devtools console run `localStorage.removeItem('hiresense.filters_seeded')`, then reload `/dashboard/ingestion`.
3. Expected: with a CV uploaded, the seniority chips for the inferred band light up and the max-years input is pre-filled. Reload again → values persist and are not re-applied over manual changes.
4. Clear all → reload → filters stay cleared (marker prevents re-seed).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.ts
git commit -m "feat(ingestion): seed filters from profile on first load"
```

---

## Verification (whole feature)

- [ ] Backend: `cd backend && uv run pytest tests/unit/ingestion/ -q` → all pass.
- [ ] Frontend: `cd frontend && npm run build` → succeeds.
- [ ] Manual: the smoke test in Task 5 Step 6 behaves as described.

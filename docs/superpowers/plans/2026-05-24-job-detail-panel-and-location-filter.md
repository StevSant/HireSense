# Job Detail Panel Layout + Location Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Ingestion job-detail side panel layout so the action buttons stay visible, and add an opt-in "only show jobs I can apply to from my location" filter that works across all sources.

**Architecture:** Backend adds two query params (`user_location`, `strict_location`) to `JobQueryParams` and a new filter step in `filter_and_paginate` that operates on the normalized `location` string. Frontend adds a text input + checkbox to `JobFiltersComponent`, persists them in `localStorage`, and forwards them through `IngestionService.queryJobs`. The detail panel is restructured from a flex column with a competing inner scroll into a 3-row CSS grid (sticky header, scrollable body, sticky footer).

**Tech Stack:** FastAPI + Pydantic (backend), Angular 17+ standalone components with signals (frontend), pytest (backend tests).

**Spec:** `docs/superpowers/specs/2026-05-24-job-detail-panel-and-location-filter-design.md`

---

## File Structure

**Backend**
- Modify: `backend/src/hiresense/ingestion/domain/job_filter.py` — add `user_location` + `strict_location` to `JobQueryParams`, add filter step in `filter_and_paginate`.
- Modify: `backend/src/hiresense/ingestion/api/routes.py` — add the two new query params to `list_jobs` and forward them to `JobQueryParams`.
- Modify: `backend/tests/unit/ingestion/test_job_filter.py` — add tests for the strict-match filter.

**Frontend**
- Modify: `frontend/src/app/core/services/ingestion.service.ts` — extend `JobFilters` interface + `queryJobs` to send new params.
- Modify: `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.ts` — load/persist `user_location` + `strict_location` from `localStorage`, emit them in filter updates.
- Modify: `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.html` — add "My location" text input + "Only matching" checkbox.
- Modify: `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.scss` — style for the new checkbox row.
- Modify: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.html` — wrap middle sections in `.panel-body`.
- Modify: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.scss` — switch `.panel` to CSS grid, remove description `max-height`.

---

## Task 1: Backend — extend `JobQueryParams` with location-match fields

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/job_filter.py`
- Test: `backend/tests/unit/ingestion/test_job_filter.py`

- [ ] **Step 1: Write failing test for new params on the model**

Append to `backend/tests/unit/ingestion/test_job_filter.py`:

```python
def test_job_query_params_defaults_for_location_match() -> None:
    params = JobQueryParams()
    assert params.user_location is None
    assert params.strict_location is False


def test_job_query_params_accepts_location_match_fields() -> None:
    params = JobQueryParams(user_location="Chile", strict_location=True)
    assert params.user_location == "Chile"
    assert params.strict_location is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/ingestion/test_job_filter.py::test_job_query_params_defaults_for_location_match backend/tests/unit/ingestion/test_job_filter.py::test_job_query_params_accepts_location_match_fields -v`

Expected: FAIL — Pydantic raises `ValidationError` (extra fields) or `AttributeError` (no such attribute).

- [ ] **Step 3: Add the fields to `JobQueryParams`**

Edit `backend/src/hiresense/ingestion/domain/job_filter.py`. Inside the `JobQueryParams` class, append two new fields after `date_to`:

```python
class JobQueryParams(BaseModel):
    page: int = 1
    page_size: int = 20
    source: str | None = None
    keyword: str | None = None
    location: str | None = None
    skills: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    user_location: str | None = None
    strict_location: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/ingestion/test_job_filter.py::test_job_query_params_defaults_for_location_match backend/tests/unit/ingestion/test_job_filter.py::test_job_query_params_accepts_location_match_fields -v`

Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/job_filter.py backend/tests/unit/ingestion/test_job_filter.py
git commit -m "feat(ingestion): add user_location and strict_location to JobQueryParams"
```

---

## Task 2: Backend — strict-match filter logic in `filter_and_paginate`

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/job_filter.py`
- Test: `backend/tests/unit/ingestion/test_job_filter.py`

- [ ] **Step 1: Write failing tests for the strict-match behavior**

Append to `backend/tests/unit/ingestion/test_job_filter.py`:

```python
def test_strict_location_off_is_no_op() -> None:
    jobs = [
        _job(id="1", location="Remote (Remote)"),
        _job(id="2", location="Chile"),
        _job(id="3", location="USA only"),
    ]
    params = JobQueryParams(user_location="Chile", strict_location=False)
    result = filter_and_paginate(jobs, params)
    assert result.total == 3


def test_strict_location_requires_user_location_set() -> None:
    jobs = [_job(id="1", location="USA only"), _job(id="2", location="Chile")]
    params = JobQueryParams(user_location=None, strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 2


def test_strict_location_includes_empty_location() -> None:
    jobs = [_job(id="1", location="")]
    params = JobQueryParams(user_location="Chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 1


def test_strict_location_includes_worldwide_keywords() -> None:
    jobs = [
        _job(id="1", location="Worldwide"),
        _job(id="2", location="Remote - Anywhere"),
        _job(id="3", location="Global remote"),
    ]
    params = JobQueryParams(user_location="Chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 3


def test_strict_location_includes_user_country_substring() -> None:
    jobs = [
        _job(id="1", location="Chile"),
        _job(id="2", location="Chile (Remote)"),
        _job(id="3", location="Latin America - Chile, Peru"),
    ]
    params = JobQueryParams(user_location="Chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 3


def test_strict_location_excludes_non_matching() -> None:
    jobs = [
        _job(id="1", location="USA only"),
        _job(id="2", location="Remote (Remote)"),
        _job(id="3", location="Europe"),
    ]
    params = JobQueryParams(user_location="Chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 0


def test_strict_location_case_insensitive() -> None:
    jobs = [
        _job(id="1", location="CHILE"),
        _job(id="2", location="chile"),
        _job(id="3", location="WORLDWIDE"),
    ]
    params = JobQueryParams(user_location="chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 3


def test_strict_location_trims_user_location() -> None:
    jobs = [_job(id="1", location="Chile"), _job(id="2", location="USA")]
    params = JobQueryParams(user_location="  Chile  ", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 1
    assert result.jobs[0].location == "Chile"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/unit/ingestion/test_job_filter.py -k "strict_location" -v`

Expected: PASS only on `test_strict_location_off_is_no_op` and `test_strict_location_requires_user_location_set` (they exercise behavior that already works); FAIL on the rest because the strict filter doesn't exist yet.

Actually `test_strict_location_excludes_non_matching` will fail because all 3 jobs currently pass through (no filter applied) — `result.total == 3`, not `0`. Confirm fail mode.

- [ ] **Step 3: Add the filter step to `filter_and_paginate`**

In `backend/src/hiresense/ingestion/domain/job_filter.py`, locate the `filter_and_paginate` function and add the new filter block immediately **after** the existing `params.date_to` block (line 67 in current code) and **before** the `total = len(filtered)` line.

```python
    if params.strict_location and params.user_location:
        user_loc = params.user_location.strip().lower()
        open_keywords = ("worldwide", "anywhere", "global")

        def _is_open(job_location: str) -> bool:
            if not job_location:
                return True
            loc = job_location.lower()
            if any(kw in loc for kw in open_keywords):
                return True
            return user_loc in loc

        filtered = [j for j in filtered if _is_open(j.location)]
```

- [ ] **Step 4: Run all strict-location tests to verify they pass**

Run: `uv run pytest backend/tests/unit/ingestion/test_job_filter.py -k "strict_location" -v`

Expected: PASS (all 8 tests).

- [ ] **Step 5: Run the full job-filter test file to confirm no regression**

Run: `uv run pytest backend/tests/unit/ingestion/test_job_filter.py -v`

Expected: PASS (all tests, including the pre-existing ones).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/job_filter.py backend/tests/unit/ingestion/test_job_filter.py
git commit -m "feat(ingestion): strict location-match filter in filter_and_paginate"
```

---

## Task 3: Backend — surface the new params on the `/ingestion/jobs` route

**Files:**
- Modify: `backend/src/hiresense/ingestion/api/routes.py`
- Test: `backend/tests/unit/ingestion/test_routes.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/unit/ingestion/test_routes.py`. The file uses `_make_app()` which builds a fresh app + fake orchestrator/scanner per test. The existing `FakeOrchestrator.list_jobs()` returns a single `BOARD_JOB` with `location="Remote"`. To exercise the strict filter we need an orchestrator that returns multiple jobs with varied locations — define a local fake inline for the new test:

```python
@pytest.mark.asyncio
async def test_list_jobs_strict_location_filters_non_matching() -> None:
    chile_job = NormalizedJob(
        id="job-chile",
        title="Chile Engineer",
        company="Co",
        description="Job",
        skills=[],
        location="Chile (Remote)",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/chile",
    )
    restricted_job = NormalizedJob(
        id="job-restricted",
        title="USA Only Engineer",
        company="Co",
        description="Job",
        skills=[],
        location="USA only",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/usa",
    )
    ambiguous_remote_job = NormalizedJob(
        id="job-remote-remote",
        title="Remote Remote Engineer",
        company="Co",
        description="Job",
        skills=[],
        location="Remote (Remote)",
        source="getonboard",
        source_type="api",
        language="en",
        url="https://example.com/getonboard",
    )
    worldwide_job = NormalizedJob(
        id="job-worldwide",
        title="Global Engineer",
        company="Co",
        description="Job",
        skills=[],
        location="Worldwide",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/global",
    )

    class MultiJobOrchestrator:
        async def run(self, filters=None) -> list[NormalizedJob]:
            return []

        def list_jobs(self) -> list[NormalizedJob]:
            return [chile_job, restricted_job, ambiguous_remote_job, worldwide_job]

    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: MultiJobOrchestrator()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/ingestion/jobs",
            params={"tab": "boards", "user_location": "Chile", "strict_location": "true"},
        )

    assert resp.status_code == 200
    data = resp.json()
    returned_ids = {j["id"] for j in data["jobs"]}
    assert returned_ids == {"job-chile", "job-worldwide"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/ingestion/test_routes.py::test_list_jobs_strict_location_filters_non_matching -v`

Expected: FAIL — the route doesn't yet accept `user_location` / `strict_location`. Depending on FastAPI behavior, either the unknown params are silently ignored and all four jobs come back (`returned_ids == 4 ids`), or the test fails on the assertion. Either way it should not pass.

- [ ] **Step 3: Update the route signature**

In `backend/src/hiresense/ingestion/api/routes.py`, the `list_jobs` function (currently lines 52–77). Add two new parameters and forward them into `JobQueryParams`:

```python
@router.get("/jobs", response_model=PaginatedResult)
async def list_jobs(
    tab: Annotated[Literal["boards", "portals"], Query()],
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
    page: int = 1,
    page_size: int = 20,
    source: str | None = None,
    keyword: str | None = None,
    location: str | None = None,
    skills: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_location: str | None = None,
    strict_location: bool = False,
) -> PaginatedResult:
    all_jobs = orchestrator.list_jobs() if tab == "boards" else scanner.list_jobs()
    params = JobQueryParams(
        page=page,
        page_size=page_size,
        source=source,
        keyword=keyword,
        location=location,
        skills=skills,
        date_from=date_from,
        date_to=date_to,
        user_location=user_location,
        strict_location=strict_location,
    )
    return filter_and_paginate(all_jobs, params)
```

- [ ] **Step 4: Run the route test to verify it passes**

Run: `uv run pytest backend/tests/unit/ingestion/test_routes.py::test_list_jobs_strict_location_filters_non_matching -v`

Expected: PASS.

- [ ] **Step 5: Run the full ingestion unit suite to confirm no regression**

Run: `uv run pytest backend/tests/unit/ingestion -v`

Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ingestion/api/routes.py backend/tests/unit/ingestion/test_routes.py
git commit -m "feat(ingestion): expose user_location and strict_location on jobs endpoint"
```

---

## Task 4: Frontend — extend `JobFilters` interface and `queryJobs`

**Files:**
- Modify: `frontend/src/app/core/services/ingestion.service.ts`

- [ ] **Step 1: Extend the `JobFilters` interface**

In `frontend/src/app/core/services/ingestion.service.ts`, replace the existing `JobFilters` interface with:

```ts
export interface JobFilters {
  source?: string;
  keyword?: string;
  location?: string;
  skills?: string;
  date_from?: string;
  date_to?: string;
  user_location?: string;
  strict_location?: boolean;
}
```

- [ ] **Step 2: Forward the new params in `queryJobs`**

In the same file, locate the `queryJobs` method (currently lines 31–50). Inside the body, after the existing `if (filters.date_to) ...` line, add:

```ts
    if (filters.user_location) params = params.set('user_location', filters.user_location);
    if (filters.strict_location) params = params.set('strict_location', 'true');
```

Note: only send `strict_location` when it's truthy. Sending `false` is unnecessary because the backend default is `false`.

- [ ] **Step 3: Verify the frontend type-checks**

Run from the frontend directory: `npm run build` (or whatever the project uses — check `frontend/package.json` for the build script; commonly `ng build`).

If a leaner check exists (e.g., `npm run typecheck` or `tsc --noEmit`), prefer it. Expected: build/typecheck succeeds with no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/core/services/ingestion.service.ts
git commit -m "feat(ingestion): extend JobFilters and queryJobs with location-match params"
```

---

## Task 5: Frontend — UI controls + localStorage persistence in `JobFiltersComponent`

**Files:**
- Modify: `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.ts`
- Modify: `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.html`
- Modify: `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.scss`
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.ts`

- [ ] **Step 1: Add localStorage keys + persistence helpers + handlers in the component class**

Replace the contents of `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.ts` with:

```ts
import { Component, OnInit, input, output } from '@angular/core';
import { JobFilters } from '../../../../core/services/ingestion.service';

const LS_USER_LOCATION = 'hiresense.user_location';
const LS_STRICT_LOCATION = 'hiresense.strict_location_match';

@Component({
  selector: 'app-job-filters',
  standalone: true,
  imports: [],
  templateUrl: './job-filters.component.html',
  styleUrl: './job-filters.component.scss',
})
export class JobFiltersComponent implements OnInit {
  sources = input.required<string[]>();
  filters = input.required<JobFilters>();

  filtersChange = output<JobFilters>();

  private debounceTimer: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    const storedLocation = localStorage.getItem(LS_USER_LOCATION) ?? '';
    const storedStrict = localStorage.getItem(LS_STRICT_LOCATION) === 'true';
    if (storedLocation || storedStrict) {
      this.emitFilters({
        user_location: storedLocation || undefined,
        strict_location: storedStrict || undefined,
      });
    }
  }

  onSourceChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const value = select.value;
    this.emitFilters({ source: value || undefined });
  }

  onKeywordInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    this.debounceEmit({ keyword: value || undefined });
  }

  onLocationInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    this.debounceEmit({ location: value || undefined });
  }

  onSkillsInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    this.debounceEmit({ skills: value || undefined });
  }

  onDateFromChange(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.emitFilters({ date_from: value || undefined });
  }

  onDateToChange(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.emitFilters({ date_to: value || undefined });
  }

  onUserLocationInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    if (value) {
      localStorage.setItem(LS_USER_LOCATION, value);
    } else {
      localStorage.removeItem(LS_USER_LOCATION);
    }
    this.debounceEmit({ user_location: value || undefined });
  }

  onStrictLocationChange(event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    localStorage.setItem(LS_STRICT_LOCATION, checked ? 'true' : 'false');
    this.emitFilters({ strict_location: checked || undefined });
  }

  clearAll(): void {
    const userLocation = localStorage.getItem(LS_USER_LOCATION) ?? '';
    const strict = localStorage.getItem(LS_STRICT_LOCATION) === 'true';
    this.filtersChange.emit({
      user_location: userLocation || undefined,
      strict_location: strict || undefined,
    });
  }

  private emitFilters(partial: Partial<JobFilters>): void {
    this.filtersChange.emit({ ...this.filters(), ...partial });
  }

  private debounceEmit(partial: Partial<JobFilters>): void {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => this.emitFilters(partial), 300);
  }
}
```

Key behaviors locked in here:
- On init, hydrate from localStorage and emit so the parent immediately filters with the stored values.
- "My location" input writes to localStorage on every keystroke.
- Strict checkbox writes immediately on change.
- `clearAll()` preserves the user's location preferences (they're settings, not session filters) — only the search-style filters reset.

- [ ] **Step 2: Add the two new controls to the template**

Replace the contents of `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.html` with:

```html
<div class="filters-bar">
  <div class="filter-item">
    <label class="filter-label">Source</label>
    <select (change)="onSourceChange($event)" class="filter-control">
      <option value="">All sources</option>
      @for (source of sources(); track source) {
        <option [value]="source" [selected]="filters().source === source">{{ source }}</option>
      }
    </select>
  </div>

  <div class="filter-item">
    <label class="filter-label">Keyword</label>
    <input
      type="text"
      [value]="filters().keyword ?? ''"
      (input)="onKeywordInput($event)"
      placeholder="Search title, description..."
      class="filter-control"
    />
  </div>

  <div class="filter-item">
    <label class="filter-label">Location</label>
    <input
      type="text"
      [value]="filters().location ?? ''"
      (input)="onLocationInput($event)"
      placeholder="e.g. Remote, USA..."
      class="filter-control"
    />
  </div>

  <div class="filter-item">
    <label class="filter-label">Skills</label>
    <input
      type="text"
      [value]="filters().skills ?? ''"
      (input)="onSkillsInput($event)"
      placeholder="Python, React..."
      class="filter-control"
    />
  </div>

  <div class="filter-item">
    <label class="filter-label">Date From</label>
    <input
      type="date"
      [value]="filters().date_from ?? ''"
      (change)="onDateFromChange($event)"
      class="filter-control"
    />
  </div>

  <div class="filter-item">
    <label class="filter-label">Date To</label>
    <input
      type="date"
      [value]="filters().date_to ?? ''"
      (change)="onDateToChange($event)"
      class="filter-control"
    />
  </div>

  <div class="filter-item filter-item-clear">
    <button (click)="clearAll()" class="btn-clear">Clear all</button>
  </div>
</div>

<div class="location-pref-bar">
  <div class="filter-item">
    <label class="filter-label">My location</label>
    <input
      type="text"
      [value]="filters().user_location ?? ''"
      (input)="onUserLocationInput($event)"
      placeholder="e.g. Chile, USA, Spain"
      class="filter-control"
    />
  </div>
  <label class="strict-toggle">
    <input
      type="checkbox"
      [checked]="filters().strict_location ?? false"
      (change)="onStrictLocationChange($event)"
    />
    <span>Only show jobs I can apply to from my location</span>
  </label>
</div>
```

- [ ] **Step 3: Style the new row**

Append to `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.scss`:

```scss
.location-pref-bar {
  display: flex;
  align-items: flex-end;
  gap: 1rem;
  padding: 0.75rem 1.25rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  margin-bottom: 1rem;
  flex-wrap: wrap;

  .filter-item {
    min-width: 200px;
    max-width: 280px;
  }
}

.strict-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  cursor: pointer;
  padding-bottom: 0.375rem;

  input[type="checkbox"] {
    width: auto;
    margin: 0;
    cursor: pointer;
  }

  span {
    user-select: none;
  }
}
```

- [ ] **Step 4: Confirm the parent passes filters through unchanged**

Open `frontend/src/app/pages/ingestion/ingestion.component.ts` and verify the `onFiltersChange` handler (line 147) merges/replaces filters as expected. Current code:

```ts
onFiltersChange(newFilters: JobFilters): void {
  this.filters.set(newFilters);
  this.page.set(1);
  this.loadJobs();
}
```

This already replaces the full filter object, so the new `user_location` and `strict_location` propagate without changes. No edit needed — just confirm.

- [ ] **Step 5: Type-check the frontend**

Run from the frontend directory: `npm run build` (or the project's typecheck script).

Expected: succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/pages/ingestion/components/job-filters/
git commit -m "feat(ingestion): add user location + strict-match toggle with localStorage persistence"
```

---

## Task 6: Frontend — restructure the job-detail panel layout

**Files:**
- Modify: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.html`
- Modify: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.scss`

- [ ] **Step 1: Wrap the scrollable middle in `.panel-body`**

Replace the contents of `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.html` with:

```html
<div class="panel-overlay" (click)="onOverlayClick($event)">
  <div class="panel">
    <!-- Header -->
    <div class="panel-header">
      <div>
        <h2 class="panel-title">{{ job().title }}</h2>
        <p class="panel-company">{{ job().company }}</p>
      </div>
      <button (click)="close.emit()" class="btn-close">✕</button>
    </div>

    <!-- Scrollable body -->
    <div class="panel-body">
      <!-- Meta grid -->
      <div class="panel-section meta-grid">
        <div class="meta-item">
          <span class="meta-label">Location</span>
          <span class="meta-value">{{ job().location || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Posted</span>
          <span class="meta-value">{{ job().posted_date ? (job().posted_date | date:'longDate') : '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Salary Range</span>
          <span class="meta-value">{{ job().salary_range || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Department</span>
          <span class="meta-value">{{ job().department || '—' }}</span>
        </div>
      </div>

      <!-- Source -->
      <div class="panel-section">
        <span class="section-label">Source</span>
        <div class="source-badges">
          <span class="badge source-badge">{{ job().source }}</span>
          <span class="badge type-badge">{{ job().source_type }}</span>
          @if (job().platform) {
            <span class="badge platform-badge">{{ job().platform }}</span>
          }
        </div>
        @if (job().categories.length > 0) {
          <div class="category-tags">
            @for (cat of job().categories; track cat) {
              <span class="badge category-badge">{{ cat }}</span>
            }
          </div>
        }
      </div>

      <!-- Skills -->
      @if (job().skills.length > 0) {
        <div class="panel-section">
          <span class="section-label">Skills</span>
          <div class="skill-chips">
            @for (skill of job().skills; track skill) {
              <span class="skill-tag">{{ skill }}</span>
            }
          </div>
        </div>
      }

      <!-- Description -->
      <div class="panel-section">
        <span class="section-label">Description</span>
        <div class="description-text">{{ job().description }}</div>
      </div>
    </div>

    <!-- Actions -->
    <div class="panel-actions">
      <a [href]="job().url" target="_blank" rel="noopener" class="btn-primary btn-action">
        View Original ↗
      </a>
      @if (tracked()) {
        <button class="btn-tracked btn-action" disabled>Tracked ✓</button>
      } @else {
        <button (click)="onTrack()" class="btn-secondary btn-action">Track</button>
      }
    </div>
  </div>
</div>
```

- [ ] **Step 2: Switch `.panel` to grid + remove the description's competing scroll**

Replace the contents of `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.scss` with:

```scss
.panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 100;
  display: flex;
  justify-content: flex-end;
}

.panel {
  width: 460px;
  max-width: 90vw;
  height: 100%;
  background: var(--bg-card);
  border-left: 1px solid var(--border-default);
  box-shadow: var(--shadow-lg);
  display: grid;
  grid-template-rows: auto 1fr auto;
  overflow: hidden;
  animation: slideIn 0.2s var(--ease);
}

@keyframes slideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-card);
}

.panel-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.panel-company {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  font-weight: 500;
  margin: 0.25rem 0 0;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.25rem;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  line-height: 1;

  &:hover { color: var(--text-primary); }
}

.panel-body {
  overflow-y: auto;
  min-height: 0;
}

.panel-section {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-subtle);
}

.section-label {
  display: block;
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.meta-label {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  font-weight: 600;
}

.meta-value {
  font-size: 0.8125rem;
  color: var(--text-primary);
}

.source-badges,
.category-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.category-tags {
  margin-top: 0.5rem;
}

.source-badge {
  background: var(--accent-bg, #e0f2f1);
  color: var(--accent);
}

.type-badge {
  background: var(--bg-inset);
  color: var(--text-secondary);
}

.platform-badge {
  background: #dbeafe;
  color: #1e40af;
}

.category-badge {
  background: #fef3c7;
  color: #92400e;
}

.skill-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.description-text {
  font-size: 0.875rem;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-line;
}

.panel-actions {
  padding: 1.25rem 1.5rem;
  display: flex;
  gap: 0.75rem;
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-card);
}

.btn-action {
  flex: 1;
  text-align: center;
  padding: 0.625rem 1rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 500;
  text-decoration: none;
  display: inline-block;
}

.btn-tracked {
  background: var(--success-bg);
  color: var(--success);
  border: 1px solid #bbf7d0;
  cursor: default;
}
```

Key changes vs. the previous SCSS:
- `.panel`: `display: grid; grid-template-rows: auto 1fr auto; height: 100%; overflow: hidden;` (was flex column with `overflow-y: auto`).
- `.panel-body`: new — owns the single scroll region.
- `.description-text`: lost `max-height: 300px` and inner `overflow-y` so it flows naturally.
- `.panel-actions`: lost `margin-top: auto` (grid handles bottom row); gained `border-top` and background to look like a footer.

- [ ] **Step 3: Type-check the frontend**

Run from the frontend directory: `npm run build` (or the project's typecheck script).

Expected: succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/ingestion/components/job-detail-panel/
git commit -m "fix(ingestion): job detail panel uses grid layout with sticky header and footer"
```

---

## Task 7: Manual browser verification

**Files:** none — verification only.

- [ ] **Step 1: Start backend and frontend dev servers**

In separate terminals:

```bash
# Backend (from backend/)
uv run uvicorn hiresense.main:app --reload

# Frontend (from frontend/)
npm start
```

Wait until both are reachable: backend on its configured port (default `:8000`), frontend on `:4200`.

- [ ] **Step 2: Verify the detail panel layout**

1. Open `http://localhost:4200/dashboard/ingestion` in a browser.
2. Click any job row to open the side panel.
3. Confirm: header (title + company + close X) is visible at the top.
4. Confirm: `View Original` and `Track` buttons are visible at the bottom of the panel.
5. Scroll inside the panel — only the middle section (`.panel-body`) scrolls; the header and the actions footer stay in place.
6. Open a job with a long description (e.g., the getonbrd Full-Stack Software Engineer job). Confirm scrolling reaches the end of the description without losing the actions footer.

If the actions footer disappears or the header scrolls away, the grid/`min-height: 0` setup is wrong — re-check Task 6 Step 2.

- [ ] **Step 3: Verify the location filter — strict OFF**

1. Reload the page.
2. In the new "My location" input, type `Chile`.
3. Leave the "Only show jobs I can apply to from my location" checkbox **unchecked**.
4. Confirm the jobs list still shows jobs with locations like `Remote (Remote)`, `Chile`, `USA`, etc. — no filtering should happen because strict is off.

- [ ] **Step 4: Verify the location filter — strict ON**

1. Tick the checkbox.
2. Confirm jobs with location `Remote (Remote)`, `USA only`, `Europe`, etc. **disappear** from the list.
3. Confirm jobs with location `Chile`, `Chile (Remote)`, `Worldwide`, `Latin America - Chile`, or empty location **remain**.
4. Pick a previously-visible getonbrd job tagged `Remote (Remote)` and confirm it is gone from the list.

- [ ] **Step 5: Verify persistence across refresh**

1. Refresh the page (F5).
2. Confirm the "My location" input still shows `Chile` and the checkbox is still ticked.
3. Confirm the filtered list matches the strict-on view from Step 4.

- [ ] **Step 6: Verify `Clear all` does not wipe location preferences**

1. Add a keyword filter (e.g., type `engineer` in the Keyword input) and confirm results filter further.
2. Click `Clear all`.
3. Confirm the keyword input clears but `My location` and the strict checkbox are still set.

- [ ] **Step 7: Verify untoggling restores the full list**

1. Untick the strict checkbox.
2. Confirm the previously-excluded jobs (`Remote (Remote)`, `USA only`, etc.) reappear.

- [ ] **Step 8: Document any visual oddities**

If any styling looks off (uneven padding on the new filter row, awkward wrapping at narrow widths, etc.), capture a screenshot and fix in a follow-up commit before declaring the task complete.

- [ ] **Step 9: Stop the dev servers**

Kill both dev server processes.

---

## Final verification

- [ ] **Step 1: Run the full backend test suite**

```bash
uv run pytest backend/tests
```

Expected: PASS (or no new failures vs. baseline).

- [ ] **Step 2: Run the frontend build one last time**

```bash
cd frontend && npm run build
```

Expected: succeeds, no new warnings.

- [ ] **Step 3: Confirm git history is clean**

```bash
git log --oneline -10
```

Expected: 6 new commits (one per Task 1–6) on top of `f8f198c`. Task 7 is verification-only — no commit unless visual fixes were needed.

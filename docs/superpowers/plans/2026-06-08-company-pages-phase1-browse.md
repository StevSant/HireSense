# Company Pages — Phase 1 (Browse) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make best-fit companies/roles in the analytics Focus card actionable — a company opens a dedicated page listing that company's open jobs with match scores; a role opens the ingestion list pre-filtered to that role.

**Architecture:** Add a `company` filter to the existing scored jobs API. A new read-only `/dashboard/company/:name` Angular page fetches that company's jobs (both `boards` + `portals` tabs, merged) via the existing `IngestionService.queryJobs` and computes a summary header client-side. Focus-card labels become router links. No new backend module, no persistence (that's Phase 2).

**Tech Stack:** FastAPI + Pydantic (backend), Angular 21 standalone + signals (frontend), pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-08-company-pages-and-following-design.md`

**Conventions:**
- Backend tests run with `uv run python -m pytest …` (bare `pytest`/`alembic` trampolines are broken on this machine).
- Frontend tests: `npm test -- --watch=false --include "<glob>"` from `frontend/`.
- Lint gates: `uv run ruff check .` (backend, from `backend/`) and `npx ng lint` (frontend, from `frontend/`) — CI runs `ng lint`, which `npm test`/`build` skip.
- Commits: Conventional Commits, scope `ingestion` (backend filter) / `analytics` (company page wiring).

---

## Task 1: Backend — `company` filter in `filter_and_paginate`

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/job_filter.py`
- Test: `backend/tests/unit/ingestion/test_job_filter.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/ingestion/test_job_filter.py` (the `_job(...)` factory already exists at the top of the file and accepts a `company=` kwarg):

```python
def test_company_filter_is_exact_and_case_insensitive() -> None:
    jobs = [
        _job(id="1", company="Coderslab.io"),
        _job(id="2", company="coderslab.io"),
        _job(id="3", company="Coderslab LATAM"),
        _job(id="4", company="Other Co"),
    ]
    params = JobQueryParams(company="  CODERSLAB.IO ")
    result = filter_and_paginate(jobs, params)
    assert {j.id for j in result.jobs} == {"1", "2"}  # trimmed, case-insensitive, exact
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/ingestion/test_job_filter.py::test_company_filter_is_exact_and_case_insensitive -v` (from `backend/`)
Expected: FAIL — `company` is dropped (Pydantic ignores the unknown field), so no filtering happens and all 4 jobs are returned.

- [ ] **Step 3: Add the field**

In `job_filter.py`, in `class JobQueryParams`, add the field directly under `source`:

```python
    source: str | None = None
    company: str | None = None
```

- [ ] **Step 4: Add the filter**

In `job_filter.py`, in `filter_and_paginate`, add this block immediately after the `if params.source:` block (around line 76):

```python
    if params.company:
        target = params.company.strip().lower()
        filtered = [j for j in filtered if j.company.strip().lower() == target]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/ingestion/test_job_filter.py -v` (from `backend/`)
Expected: PASS (all tests in the file).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/job_filter.py backend/tests/unit/ingestion/test_job_filter.py
git commit -m "feat(ingestion): add company filter to job query"
```

---

## Task 2: Backend — expose `company` on `GET /ingestion/jobs`

**Files:**
- Modify: `backend/src/hiresense/ingestion/api/routes.py` (handler `list_jobs`, ~line 138; `JobQueryParams(...)` construction, ~line 245)
- Test: `backend/tests/integration/test_jobs_company_filter.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/test_jobs_company_filter.py` (mirrors the existing `test_ingestion_to_api_flow.py` harness — a real orchestrator over sqlite behind the real route):

```python
"""Integration: GET /ingestion/jobs?company= narrows to one company."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.infrastructure.database import Base
from hiresense.ingestion.api import (
    get_ingestion_orchestrator,
    get_portal_scanner,
    router,
)
from hiresense.ingestion.api.dependencies import get_semantic_scoring
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.ingestion.infrastructure import JobsRepository
from hiresense.ingestion.infrastructure.models import IngestedJob  # noqa: F401 (registers table)
from hiresense.kernel.value_objects import SourceType
from hiresense.profile.api.dependencies import get_profile_service


class _FakeBus:
    async def publish(self, event) -> None:  # noqa: ARG002
        pass


class _FakeSource:
    def source_name(self) -> str:
        return "remotive"

    def source_type(self) -> SourceType:
        return SourceType.API

    def supports_snapshot_closure(self) -> bool:
        return False

    async def fetch_jobs(self, filters=None) -> list[RawJobListing]:  # noqa: ARG002
        return [
            RawJobListing(source="remotive", source_id="101",
                          raw_data={"title": "Backend Engineer", "company": "Acme",
                                    "url": "https://e.com/101"}),
            RawJobListing(source="remotive", source_id="102",
                          raw_data={"title": "Frontend Engineer", "company": "Beta",
                                    "url": "https://e.com/102"}),
        ]


class _Normalizer:
    def normalize(self, raw: RawJobListing) -> dict:
        return {
            "title": raw.raw_data["title"],
            "company": raw.raw_data["company"],
            "description": "Build things",
            "skills": [],
            "location": "Remote",
            "salary_range": None,
            "url": raw.raw_data["url"],
            "language": "en",
        }


class _FakeProfileService:
    async def list_profiles(self):
        return []


class _EmptyScanner:
    def list_jobs(self):
        return []

    def get_job_by_id(self, job_id):  # noqa: ARG002
        return None


@pytest.mark.asyncio
async def test_company_query_param_narrows_results() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo = JobsRepository(session_factory=session_factory, bucket="boards")
    orchestrator = IngestionOrchestrator(
        sources=[_FakeSource()],
        normalizers={"remotive": _Normalizer()},
        event_bus=_FakeBus(),
        repository=repo,
        cooldown_seconds=0,
    )
    await orchestrator.run()

    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_portal_scanner] = lambda: _EmptyScanner()
    app.dependency_overrides[get_profile_service] = lambda: _FakeProfileService()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/ingestion/jobs", params={"tab": "boards", "min_score": 0, "company": "Acme"}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert {j["title"] for j in body["jobs"]} == {"Backend Engineer"}

    Base.metadata.drop_all(engine)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/integration/test_jobs_company_filter.py -v` (from `backend/`)
Expected: FAIL — the route ignores the unknown `company` query param, so both jobs return (`total == 2`).

- [ ] **Step 3: Add the route parameter**

In `routes.py`, in the `list_jobs` signature, add `company` directly under `source` (around line 150):

```python
    source: str | None = None,
    company: str | None = None,
    keyword: str | None = None,
```

- [ ] **Step 4: Thread it into `JobQueryParams`**

In `routes.py`, in the `JobQueryParams(...)` construction (around line 245), add `company=company,` directly under `source=source,`:

```python
        source=source,
        company=company,
        keyword=keyword,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python -m pytest tests/integration/test_jobs_company_filter.py -v` (from `backend/`)
Expected: PASS (`total == 1`).

- [ ] **Step 6: Lint + commit**

```bash
cd backend && uv run ruff check . && cd ..
git add backend/src/hiresense/ingestion/api/routes.py backend/tests/integration/test_jobs_company_filter.py
git commit -m "feat(ingestion): accept company query param on jobs endpoint"
```

---

## Task 3: Frontend — `company` in `JobFilters` + `IngestionService`

**Files:**
- Modify: `frontend/src/app/pages/ingestion/models/job-filters.model.ts`
- Modify: `frontend/src/app/core/services/ingestion.service.ts` (~line 50)
- Test: `frontend/src/app/core/services/ingestion.service.spec.ts`

- [ ] **Step 1: Write the failing test**

Append inside the `describe('IngestionService', …)` block in `ingestion.service.spec.ts`:

```typescript
  it('queryJobs sends the company filter param', () => {
    service.queryJobs('boards', 1, 100, { company: 'Acme' }).subscribe();
    const req = httpMock.expectOne((r) => r.url === `${environment.apiUrl}/ingestion/jobs`);
    expect(req.request.params.get('company')).toBe('Acme');
    req.flush(empty);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --watch=false --include "**/ingestion.service.spec.ts"` (from `frontend/`)
Expected: FAIL — `{ company: 'Acme' }` is not assignable to `JobFilters` (TS build error).

- [ ] **Step 3: Add the field to the model**

In `job-filters.model.ts`, add under `source?`:

```typescript
export interface JobFilters {
  source?: string;
  company?: string;
  keyword?: string;
```

- [ ] **Step 4: Send it in `queryJobs`**

In `ingestion.service.ts`, add directly after the `filters.source` line (~line 50):

```typescript
    if (filters.source) params = params.set('source', filters.source);
    if (filters.company) params = params.set('company', filters.company);
    if (filters.keyword) params = params.set('keyword', filters.keyword);
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test -- --watch=false --include "**/ingestion.service.spec.ts"` (from `frontend/`)
Expected: PASS (all 4 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/pages/ingestion/models/job-filters.model.ts frontend/src/app/core/services/ingestion.service.ts frontend/src/app/core/services/ingestion.service.spec.ts
git commit -m "feat(ingestion): thread company filter through the jobs service"
```

---

## Task 4: Frontend — ingestion pre-fills the `keyword` filter from query param

**Files:**
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.ts` (`ngOnInit`, ~line 115)

> No unit test: `IngestionComponent` is heavily wired (multiple injected services, debounced refetch) and has no existing spec; a meaningful isolated test would be disproportionate. This is a 3-line, low-risk change verified live in Task 7 (role link → ingestion lands with the keyword pre-filled). Keep the change minimal.

- [ ] **Step 1: Add the query-param read**

In `ingestion.component.ts`, add a call in `ngOnInit` **before** `this.loadJobs();`:

```typescript
  ngOnInit(): void {
    this.feedbackRefetch$
      .pipe(debounceTime(environment.feedbackRefetchDebounceMs), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.loadJobs());
    this.loadPortals();
    this.applyKeywordFromQueryParam();
    this.loadJobs();
    this.openDetailFromQueryParam();
  }

  private applyKeywordFromQueryParam(): void {
    const keyword = this.route.snapshot.queryParamMap.get('keyword');
    if (keyword) this.filters.set({ ...this.filters(), keyword });
  }
```

(`this.filters` is the existing writable signal — `switchTab` already calls `this.filters.set({})`. `this.route` is the existing injected `ActivatedRoute`.)

- [ ] **Step 2: Verify it builds + lints**

Run: `npx ng lint` (from `frontend/`)
Expected: "All files pass linting."

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/ingestion/ingestion.component.ts
git commit -m "feat(ingestion): pre-fill keyword filter from query param"
```

---

## Task 5: Frontend — `CompanyComponent` + route

**Files:**
- Create: `frontend/src/app/pages/company/company.component.ts`
- Create: `frontend/src/app/pages/company/company.component.html`
- Create: `frontend/src/app/pages/company/company.component.scss`
- Create: `frontend/src/app/pages/company/company.component.spec.ts`
- Modify: `frontend/src/app/app.routes.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/pages/company/company.component.spec.ts`:

```typescript
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of, throwError } from 'rxjs';
import { CompanyComponent } from './company.component';
import { IngestionService } from '../../core/services/ingestion.service';

function job(over: Record<string, unknown> = {}) {
  return {
    id: '1', title: 'Backend Engineer', company: 'Acme', description: '', skills: [],
    location: 'Remote', salary_range: null, source: 'remotive', source_type: 'api',
    platform: null, categories: [], department: null, url: 'https://e.com/1',
    posted_date: null, match_score: 0.82, llm_score: null, verdict: null,
    reasons: [], dealbreakers: [], status: 'open', ...over,
  };
}

function page(jobs: unknown[]) {
  return { jobs, total: jobs.length, page: 1, page_size: 100, total_pages: 1 };
}

function mount(service: unknown, name = 'Acme') {
  TestBed.configureTestingModule({
    imports: [CompanyComponent],
    providers: [
      provideRouter([]),
      { provide: IngestionService, useValue: service },
      { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ name }) } } },
    ],
  });
  const fixture = TestBed.createComponent(CompanyComponent);
  fixture.detectChanges();
  return fixture;
}

describe('CompanyComponent', () => {
  it('renders the company name, summary and a job row', () => {
    const service = {
      queryJobs: (tab: string) => of(page(tab === 'boards' ? [job()] : [])),
    };
    const fixture = mount(service);
    expect(fixture.nativeElement.textContent).toContain('Acme');
    expect(fixture.nativeElement.querySelectorAll('.company-job').length).toBe(1);
    expect(fixture.nativeElement.textContent).toContain('82%');
  });

  it('merges boards + portals and de-dupes by id', () => {
    const service = {
      queryJobs: (tab: string) =>
        of(page(tab === 'boards' ? [job({ id: '1' })] : [job({ id: '1' }), job({ id: '2' })])),
    };
    const fixture = mount(service);
    expect(fixture.nativeElement.querySelectorAll('.company-job').length).toBe(2);
  });

  it('shows the empty state when the company has no jobs', () => {
    const service = { queryJobs: () => of(page([])) };
    const fixture = mount(service);
    expect(fixture.nativeElement.querySelector('.company-state')).not.toBeNull();
    expect(fixture.nativeElement.querySelectorAll('.company-job').length).toBe(0);
  });

  it('shows the error state when a request fails', () => {
    const service = { queryJobs: () => throwError(() => new Error('boom')) };
    const fixture = mount(service);
    expect(fixture.nativeElement.querySelector('.company-state-error')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --watch=false --include "**/company.component.spec.ts"` (from `frontend/`)
Expected: FAIL — `CompanyComponent` does not exist yet.

- [ ] **Step 3: Create the component**

Create `frontend/src/app/pages/company/company.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { forkJoin } from 'rxjs';
import { IngestionService } from '../../core/services/ingestion.service';
import { NormalizedJob } from '../ingestion/models/normalized-job.model';

const PERCENT = 100;
/** A single company's open-job count is small once filtered — one large page is enough. */
const COMPANY_PAGE_SIZE = 100;
const TOP_LOCATIONS = 4;

@Component({
  selector: 'app-company',
  standalone: true,
  imports: [RouterLink, DatePipe],
  templateUrl: './company.component.html',
  styleUrl: './company.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CompanyComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private ingestion = inject(IngestionService);
  private destroyRef = inject(DestroyRef);

  company = signal('');
  jobs = signal<NormalizedJob[]>([]);
  loading = signal(true);
  error = signal(false);

  scoredCount = computed(() => this.jobs().filter((j) => j.match_score !== null).length);

  avgMatchPct = computed<number | null>(() => {
    const scored = this.jobs().filter((j) => j.match_score !== null);
    if (!scored.length) return null;
    const sum = scored.reduce((acc, j) => acc + (j.match_score ?? 0), 0);
    return Math.round((sum / scored.length) * PERCENT);
  });

  topLocations = computed<{ label: string; count: number }[]>(() => {
    const counts = new Map<string, number>();
    for (const j of this.jobs()) {
      const loc = j.location?.trim();
      if (loc) counts.set(loc, (counts.get(loc) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, TOP_LOCATIONS)
      .map(([label, count]) => ({ label, count }));
  });

  ngOnInit(): void {
    const name = this.route.snapshot.paramMap.get('name') ?? '';
    this.company.set(name);
    if (!name) {
      this.error.set(true);
      this.loading.set(false);
      return;
    }
    forkJoin({
      boards: this.ingestion.queryJobs('boards', 1, COMPANY_PAGE_SIZE, { company: name, sort: 'match_desc' }),
      portals: this.ingestion.queryJobs('portals', 1, COMPANY_PAGE_SIZE, { company: name, sort: 'match_desc' }),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ boards, portals }) => {
          const byId = new Map<string, NormalizedJob>();
          for (const j of [...boards.jobs, ...portals.jobs]) byId.set(j.id, j);
          this.jobs.set(
            [...byId.values()].sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0)),
          );
          this.loading.set(false);
        },
        error: () => {
          this.error.set(true);
          this.loading.set(false);
        },
      });
  }

  matchPct(job: NormalizedJob): number | null {
    return job.match_score === null ? null : Math.round(job.match_score * PERCENT);
  }
}
```

- [ ] **Step 4: Create the template**

Create `frontend/src/app/pages/company/company.component.html`:

```html
<div class="company-page">
  <a class="company-back" routerLink="/dashboard/analytics">← Analytics</a>

  <header class="company-header">
    <p class="company-eyebrow">Company</p>
    <h1 class="company-title">{{ company() }}</h1>
    @if (!loading() && !error() && jobs().length) {
      <p class="company-summary">
        <strong>{{ jobs().length }}</strong> open {{ jobs().length === 1 ? 'job' : 'jobs' }}
        @if (scoredCount() > 0) {
          · <strong>{{ scoredCount() }}</strong> scored for your profile
          @if (avgMatchPct() !== null) { · avg <strong>{{ avgMatchPct() }}%</strong> match }
        }
      </p>
      @if (topLocations().length) {
        <ul class="company-locations">
          @for (loc of topLocations(); track loc.label) {
            <li class="company-loc">{{ loc.label }} <span>{{ loc.count }}</span></li>
          }
        </ul>
      }
    }
  </header>

  @if (loading()) {
    <p class="company-state">Loading…</p>
  } @else if (error()) {
    <p class="company-state company-state-error">Couldn't load this company's jobs.</p>
  } @else if (!jobs().length) {
    <p class="company-state">No open jobs for this company right now.</p>
  } @else {
    <ul class="company-jobs">
      @for (job of jobs(); track job.id) {
        <li class="company-job">
          <div class="company-job-main">
            <a class="company-job-title" routerLink="/dashboard/ingestion" [queryParams]="{ job_id: job.id }">{{ job.title }}</a>
            <div class="company-job-meta">
              <span>{{ job.location }}</span>
              <span class="company-job-source">{{ job.source }}</span>
              @if (job.posted_date) { <span>{{ job.posted_date | date: 'mediumDate' }}</span> }
            </div>
          </div>
          <span class="company-job-score" [class.none]="matchPct(job) === null">
            @if (matchPct(job) !== null) { {{ matchPct(job) }}% } @else { — }
          </span>
        </li>
      }
    </ul>
  }
</div>
```

- [ ] **Step 5: Create the styles**

Create `frontend/src/app/pages/company/company.component.scss`:

```scss
.company-page { padding: 1.5rem 1.75rem 2.5rem; max-width: 880px; }

.company-back {
  display: inline-block;
  margin-bottom: 1rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
  text-decoration: none;

  &:hover { color: var(--accent); }
}

.company-header { margin-bottom: 1.5rem; }
.company-eyebrow {
  margin: 0 0 0.2rem;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--accent);
}
.company-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.9rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
.company-summary {
  margin: 0.4rem 0 0;
  font-size: 0.95rem;
  color: var(--text-secondary);

  strong { color: var(--text-primary); }
}
.company-locations {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0.75rem 0 0;
  padding: 0;
}
.company-loc {
  background: var(--bg-inset);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-full);
  padding: 0.2rem 0.65rem;
  font-size: 0.8125rem;
  color: var(--text-secondary);

  span { color: var(--text-muted); padding-left: 0.3rem; }
}

.company-state { color: var(--text-muted); font-size: 0.9rem; }
.company-state-error { color: var(--danger); }

.company-jobs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.6rem; }
.company-job {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1.1rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.company-job-title {
  font-weight: 600;
  color: var(--text-primary);
  text-decoration: none;

  &:hover { color: var(--accent); }
}
.company-job-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.25rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}
.company-job-source { text-transform: capitalize; }
.company-job-score {
  flex: none;
  font-family: var(--font-display);
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--accent-text);

  &.none { color: var(--text-muted); font-weight: 400; }
}
```

- [ ] **Step 6: Register the route**

In `app.routes.ts`, add inside the dashboard `children` array, directly after the `analytics` route (line 23):

```typescript
      { path: 'analytics', loadComponent: () => import('./pages/analytics/analytics.component').then(m => m.AnalyticsComponent) },
      { path: 'company/:name', loadComponent: () => import('./pages/company/company.component').then(m => m.CompanyComponent) },
```

- [ ] **Step 7: Run test to verify it passes**

Run: `npm test -- --watch=false --include "**/company.component.spec.ts"` (from `frontend/`)
Expected: PASS (4 tests).

- [ ] **Step 8: Lint + commit**

```bash
cd frontend && npx ng lint && cd ..
git add frontend/src/app/pages/company/ frontend/src/app/app.routes.ts
git commit -m "feat(analytics): add company detail page (jobs + match summary)"
```

---

## Task 6: Frontend — Focus-card company & role links

**Files:**
- Modify: `frontend/src/app/pages/analytics/components/search-focus/search-focus.component.ts` (add `RouterLink` import)
- Modify: `frontend/src/app/pages/analytics/components/search-focus/search-focus.component.html`
- Modify: `frontend/src/app/pages/analytics/components/search-focus/search-focus.component.scss`
- Test: `frontend/src/app/pages/analytics/components/search-focus/search-focus.component.spec.ts`

- [ ] **Step 1: Update the spec (failing test)**

In `search-focus.component.spec.ts`, change the `mount` helper to provide a router, and add a link-assertion test.

Replace the `mount` function body with:

```typescript
  function mount(f: SearchFocus) {
    TestBed.configureTestingModule({
      imports: [SearchFocusComponent],
      providers: [provideRouter([])],
    });
    const fixture = TestBed.createComponent(SearchFocusComponent);
    fixture.componentRef.setInput('focus', f);
    fixture.detectChanges();
    return fixture;
  }
```

Add the import at the top of the file:

```typescript
import { provideRouter } from '@angular/router';
```

Add this test inside the `describe` block:

```typescript
  it('links companies to their page and roles to filtered ingestion', () => {
    const fixture = mount(focus());
    const hrefs = Array.from(fixture.nativeElement.querySelectorAll('a')).map(
      (a: HTMLAnchorElement) => a.getAttribute('href'),
    );
    expect(hrefs).toContain('/dashboard/company/Acme');
    expect(hrefs.some((h) => h?.startsWith('/dashboard/ingestion') && h.includes('keyword=Backend'))).toBe(true);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --watch=false --include "**/search-focus.component.spec.ts"` (from `frontend/`)
Expected: FAIL — labels are `<span>`, not `<a>`, so no matching hrefs (and `routerLink` is not yet imported).

- [ ] **Step 3: Import RouterLink in the component**

In `search-focus.component.ts`, add the import and register it:

```typescript
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SearchFocus } from '../../models/search-focus.model';

const PERCENT = 100;

@Component({
  selector: 'app-search-focus',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './search-focus.component.html',
  styleUrl: './search-focus.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
```

- [ ] **Step 4: Turn the labels into links**

In `search-focus.component.html`, change the company list row (in the **Best-fit companies** column) from:

```html
            <li><span class="focus-label">{{ c.label }}</span><span class="focus-count">{{ c.count }}</span></li>
```

to:

```html
            <li><a class="focus-label focus-link" [routerLink]="['/dashboard/company', c.label]">{{ c.label }}</a><span class="focus-count">{{ c.count }}</span></li>
```

And change the role list row (in the **Best-fit roles** column) from:

```html
            <li><span class="focus-label">{{ r.label }}</span><span class="focus-count">{{ r.count }}</span></li>
```

to:

```html
            <li><a class="focus-label focus-link" routerLink="/dashboard/ingestion" [queryParams]="{ keyword: r.label }">{{ r.label }}</a><span class="focus-count">{{ r.count }}</span></li>
```

- [ ] **Step 5: Style the links**

In `search-focus.component.scss`, append:

```scss
.focus-link {
  text-decoration: none;
  color: var(--text-secondary);
  cursor: pointer;

  &:hover { color: var(--accent); text-decoration: underline; }
}
```

(The existing `.focus-label` rule already handles ellipsis/overflow; `.focus-link` layers the link affordance on top.)

- [ ] **Step 6: Run test to verify it passes**

Run: `npm test -- --watch=false --include "**/search-focus.component.spec.ts"` (from `frontend/`)
Expected: PASS (all tests, including the new link test).

- [ ] **Step 7: Lint + commit**

```bash
cd frontend && npx ng lint && cd ..
git add frontend/src/app/pages/analytics/components/search-focus/
git commit -m "feat(analytics): link focus companies to company page, roles to filtered jobs"
```

---

## Task 7: Full verification + live check

**No code.** Confirm the whole feature works end-to-end.

- [ ] **Step 1: Backend — full analytics + ingestion suites**

Run (from `backend/`): `uv run python -m pytest tests/unit/ingestion tests/integration/test_jobs_company_filter.py -q`
Expected: all pass.

- [ ] **Step 2: Frontend — analytics + company + ingestion-service specs**

Run (from `frontend/`): `npm test -- --watch=false --include "**/pages/analytics/**/*.spec.ts" --include "**/pages/company/**/*.spec.ts" --include "**/ingestion.service.spec.ts"`
Expected: all pass.

- [ ] **Step 3: Lint both**

Run: `cd backend && uv run ruff check . && cd ../frontend && npx ng lint && cd ..`
Expected: clean.

- [ ] **Step 4: Live check with Playwright (servers already running on :4200/:8000)**

  1. Navigate to `http://localhost:4200/dashboard/analytics` (log in as `admin`/`changeme` if redirected).
  2. In the Focus card, click a best-fit company (e.g. "Coderslab.io") → URL becomes `/dashboard/company/Coderslab.io`; the page shows the company name, a summary line (open jobs + avg match %), and a list of jobs with match-% badges.
  3. Go back; click a best-fit role (e.g. "Back End Engineer") → URL becomes `/dashboard/ingestion?keyword=Back%20End%20Engineer` and the ingestion keyword filter is pre-filled, list narrowed.
  4. Confirm no console errors.

- [ ] **Step 5: Final confirmation**

All tests green, lint clean, both click-throughs verified live. Phase 1 complete.

---

## Self-review notes

- **Spec coverage:** company filter (Tasks 1–2) ✓; dedicated company page with summary header + compact match-scored list (Task 5) ✓; both-tabs merge + client-side summary (Task 5 `ngOnInit`/computeds) ✓; company links → page, role links → ingestion `?keyword=` (Task 6) ✓; ingestion reads `keyword` (Task 4) ✓; exact case-insensitive company match (Task 1) ✓. Following/persistence intentionally deferred to Phase 2.
- **Deviation from spec:** the summary header says "scored for your profile / avg match %" and omits remote-share — the frontend `NormalizedJob` has no `remote_modality` field, so a remote count would be a shaky location-regex heuristic. Locations are shown as chips instead. Minor, noted.
- **Type consistency:** `queryJobs(tab, page, pageSize, filters, …)` signature matches Task 3; `JobFilters.company` (Task 3) is what `CompanyComponent` passes (Task 5); `match_score: number | null` drives `matchPct`/`avgMatchPct`; route `company/:name` ↔ `paramMap.get('name')`.
- **No placeholders.** Every code step is complete and runnable.

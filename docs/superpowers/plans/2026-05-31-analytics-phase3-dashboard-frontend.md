# Analytics Phase 3 — Dashboard Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/dashboard/analytics` page that renders the four `/analytics/*` endpoints — funnel, target salary, market intel, skill gap — using hand-rolled CSS/SVG charts (no charting dependency), each section loading independently with its own loading/error/empty state.

**Architecture:** A root-injectable `AnalyticsService` (mirrors `tracking.service.ts`) wraps the four GETs. Standalone OnPush chart components (`bar-chart`, `funnel-chart`, `trend-line`, `salary-band`) take typed inputs and render CSS bars / inline SVG. The `analytics` page component loads the four results independently into signals and composes four section cards. A new lazy child route + sidebar nav link surface it. One small backend addition (`current_rejected` on the funnel) closes the current-status gap flagged in the Phase 2 review.

**Tech Stack:** Angular 21 (standalone, signals, OnPush), RxJS, vitest + `@angular/build:unit-test` + `@angular/common/http/testing`; backend tweak in Python (pytest via `uv run python -m pytest`).

**Spec:** `docs/superpowers/specs/2026-05-31-market-analytics-design.md` §Architecture.3. Backend Phases 1–2 are merged; the four endpoints exist and are auth-gated.

**Tooling:** Frontend from `frontend/`: tests `npx ng test --no-watch` (NOT `npx vitest run` — it lacks the Angular globals); build `npm run build`. Backend from `backend/`: `uv run python -m pytest`.

**Conventions (verified, follow exactly):**
- Services: `@Injectable({ providedIn: 'root' })`, `constructor(private http: HttpClient) {}`, hit `` `${environment.apiUrl}/...` ``, return `Observable`s (see `core/services/tracking.service.ts`).
- Models: one interface per file under `pages/<area>/models/`, imported by direct path (no barrel).
- Components: standalone, `changeDetection: ChangeDetectionStrategy.OnPush`, separate `.html`/`.scss`, `input`/`signal`/`computed`. Destroy-safe subscriptions via `takeUntilDestroyed(inject(DestroyRef))`.
- Tests: vitest globals (`describe`/`it`/`expect`/`vi` — no imports); service tests use `provideHttpClient()` + `provideHttpClientTesting()`; component tests use `TestBed` + `fixture.componentRef.setInput(...)`.
- Routes: child routes under `dashboard` in `app.routes.ts` (lazy `loadComponent`); sidebar nav links in `dashboard.component.html` are `<a routerLink="X" routerLinkActive="active"><span class="nav-icon">…svg…</span><span>Label</span></a>`.

**Backend response shapes (mirror in TS models):**
- `FunnelMetrics{ stages: FunnelStage[], rejected: int, total_applications: int }` + (added in Task 1) `current_rejected: int`; `FunnelStage{ stage: str, reached: int, conversion_from_prev: float|null, median_days_in_stage: float|null, current: int }`.
- `MarketIntel{ top_skills: SkillCount[], remote_mix: {[k]:int}, posting_trend: TrendPoint[], salary_distribution: SalaryDistribution }`; `SkillCount{ skill, count, pct }`; `TrendPoint{ week, count }`; `SalaryDistribution{ currency: str|null, min_annual: int|null, median_annual: int|null, max_annual: int|null, parsed_count, unparsed_count, other_currency_count, disclosed_pct }`.
- `SkillGap{ has_profile: bool, missing: SkillGapItem[] }`; `SkillGapItem{ skill, count, pct }`.
- `TargetSalary{ insufficient_data: bool, currency: str|null, p25_annual: int|null, median_annual: int|null, p75_annual: int|null, sample_size: int }`.

---

## File Structure

**Backend (Task 1):**
- Modify `backend/src/hiresense/analytics/domain/funnel_service.py` (+ `current_rejected`), `backend/tests/unit/analytics/test_funnel_service.py`, `backend/tests/integration/test_analytics_endpoints.py`.

**Frontend models** (`frontend/src/app/pages/analytics/models/`): `funnel-metrics.model.ts`, `market-intel.model.ts`, `skill-gap.model.ts`, `target-salary.model.ts` (each may hold the small nested interfaces it owns).

**Service:** `frontend/src/app/core/services/analytics.service.ts` (+ `.spec.ts`).

**Chart components** (`frontend/src/app/pages/analytics/components/`): `bar-chart/`, `funnel-chart/`, `trend-line/`, `salary-band/` (each `.ts`/`.html`/`.scss` + `.spec.ts`).

**Page:** `frontend/src/app/pages/analytics/analytics.component.ts`/`.html`/`.scss` (+ `.spec.ts`).

**Wiring:** `frontend/src/app/app.routes.ts` (route), `frontend/src/app/pages/dashboard/dashboard.component.html` (nav link).

---

## Task 1: Backend — add `current_rejected` to the funnel

Closes the Phase 2 review gap: the current-status distribution must account for apps whose current status is `rejected`.

**Files:** Modify `backend/src/hiresense/analytics/domain/funnel_service.py`, `backend/tests/unit/analytics/test_funnel_service.py`.

- [ ] **Step 1: Add the failing test** (append to `test_funnel_service.py`):

```python
def test_current_rejected_counted():
    a, b = uuid_mod.uuid4(), uuid_mod.uuid4()
    rows = [
        _t(a, None, "saved", 1), _t(a, "saved", "applied", 3), _t(a, "applied", "rejected", 5),
        _t(b, None, "saved", 1),
    ]
    m = FunnelService(_FakeHistory(rows)).compute()
    # a's current status is rejected; b is still saved.
    assert m.current_rejected == 1
    current_saved = next(s.current for s in m.stages if s.stage == "saved")
    assert current_saved == 1
```

- [ ] **Step 2: Run → FAIL**

Run: `cd backend && uv run python -m pytest tests/unit/analytics/test_funnel_service.py -v`
Expected: FAIL (`current_rejected` not a field).

- [ ] **Step 3: Implement** — in `funnel_service.py`:

Add the field to `FunnelMetrics`:

```python
class FunnelMetrics(BaseModel):
    stages: list[FunnelStage]
    rejected: int
    current_rejected: int
    total_applications: int
```

In `compute`, track current-rejected. After the existing `last = to_statuses[-1]` / `current` update block, add a counter. Concretely, initialize `current_rejected = 0` near `rejected = 0`, and in the per-app loop after computing `last`:

```python
            last = to_statuses[-1]
            if last in current:
                current[last] += 1
            elif last == "rejected":
                current_rejected += 1
```

Then include it in the returned `FunnelMetrics(...)`:

```python
        return FunnelMetrics(
            stages=stages_out, rejected=rejected,
            current_rejected=current_rejected, total_applications=len(by_app),
        )
```

- [ ] **Step 4: Run → PASS.** Then update the integration test `backend/tests/integration/test_analytics_endpoints.py::test_funnel_endpoint` to assert the field is present (the seeded app is `applied`, so `current_rejected == 0`):

```python
        assert data["current_rejected"] == 0
```

- [ ] **Step 5: Run analytics slice + commit**

Run: `cd backend && uv run python -m pytest tests/unit/analytics tests/integration/test_analytics_endpoints.py -q`
Expected: PASS.

```bash
git add backend/src/hiresense/analytics/domain/funnel_service.py backend/tests/unit/analytics/test_funnel_service.py backend/tests/integration/test_analytics_endpoints.py
git commit -m "feat(analytics): add current_rejected to funnel metrics"
```

---

## Task 2: Frontend models

**Files:** Create the four model files under `frontend/src/app/pages/analytics/models/`.

- [ ] **Step 1: `funnel-metrics.model.ts`**

```typescript
export interface FunnelStage {
  stage: string;
  reached: number;
  conversion_from_prev: number | null;
  median_days_in_stage: number | null;
  current: number;
}

export interface FunnelMetrics {
  stages: FunnelStage[];
  rejected: number;
  current_rejected: number;
  total_applications: number;
}
```

- [ ] **Step 2: `market-intel.model.ts`**

```typescript
export interface SkillCount {
  skill: string;
  count: number;
  pct: number;
}

export interface TrendPoint {
  week: string;
  count: number;
}

export interface SalaryDistribution {
  currency: string | null;
  min_annual: number | null;
  median_annual: number | null;
  max_annual: number | null;
  parsed_count: number;
  unparsed_count: number;
  other_currency_count: number;
  disclosed_pct: number;
}

export interface MarketIntel {
  top_skills: SkillCount[];
  remote_mix: Record<string, number>;
  posting_trend: TrendPoint[];
  salary_distribution: SalaryDistribution;
}
```

- [ ] **Step 3: `skill-gap.model.ts`**

```typescript
export interface SkillGapItem {
  skill: string;
  count: number;
  pct: number;
}

export interface SkillGap {
  has_profile: boolean;
  missing: SkillGapItem[];
}
```

- [ ] **Step 4: `target-salary.model.ts`**

```typescript
export interface TargetSalary {
  insufficient_data: boolean;
  currency: string | null;
  p25_annual: number | null;
  median_annual: number | null;
  p75_annual: number | null;
  sample_size: number;
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/analytics/models/
git commit -m "feat(analytics-fe): add analytics frontend models"
```

---

## Task 3: AnalyticsService

**Files:** Create `frontend/src/app/core/services/analytics.service.ts` + `.spec.ts`.

- [ ] **Step 1: Write the failing test** (`analytics.service.spec.ts`)

```typescript
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { AnalyticsService } from './analytics.service';
import { environment } from '../../../environments/environment';

describe('AnalyticsService', () => {
  let service: AnalyticsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AnalyticsService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AnalyticsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('funnel GETs /analytics/funnel', () => {
    service.funnel().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/analytics/funnel`);
    expect(req.request.method).toBe('GET');
    req.flush({ stages: [], rejected: 0, current_rejected: 0, total_applications: 0 });
  });

  it('market GETs /analytics/market', () => {
    service.market().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/analytics/market`);
    expect(req.request.method).toBe('GET');
    req.flush({ top_skills: [], remote_mix: {}, posting_trend: [], salary_distribution: {
      currency: null, min_annual: null, median_annual: null, max_annual: null,
      parsed_count: 0, unparsed_count: 0, other_currency_count: 0, disclosed_pct: 0 } });
  });

  it('skillGap GETs /analytics/skill-gap', () => {
    service.skillGap().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/analytics/skill-gap`);
    expect(req.request.method).toBe('GET');
    req.flush({ has_profile: false, missing: [] });
  });

  it('targetSalary GETs /analytics/target-salary', () => {
    service.targetSalary().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/analytics/target-salary`);
    expect(req.request.method).toBe('GET');
    req.flush({ insufficient_data: true, currency: null, p25_annual: null,
      median_annual: null, p75_annual: null, sample_size: 0 });
  });
});
```

- [ ] **Step 2: Run → FAIL** (`cd frontend && npx ng test --no-watch`) — module not found.

- [ ] **Step 3: Implement** `analytics.service.ts`:

```typescript
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { FunnelMetrics } from '../../pages/analytics/models/funnel-metrics.model';
import { MarketIntel } from '../../pages/analytics/models/market-intel.model';
import { SkillGap } from '../../pages/analytics/models/skill-gap.model';
import { TargetSalary } from '../../pages/analytics/models/target-salary.model';

@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  constructor(private http: HttpClient) {}

  funnel(): Observable<FunnelMetrics> {
    return this.http.get<FunnelMetrics>(`${environment.apiUrl}/analytics/funnel`);
  }

  market(): Observable<MarketIntel> {
    return this.http.get<MarketIntel>(`${environment.apiUrl}/analytics/market`);
  }

  skillGap(): Observable<SkillGap> {
    return this.http.get<SkillGap>(`${environment.apiUrl}/analytics/skill-gap`);
  }

  targetSalary(): Observable<TargetSalary> {
    return this.http.get<TargetSalary>(`${environment.apiUrl}/analytics/target-salary`);
  }
}
```

- [ ] **Step 4: Run → PASS.** Commit:

```bash
git add frontend/src/app/core/services/analytics.service.ts frontend/src/app/core/services/analytics.service.spec.ts
git commit -m "feat(analytics-fe): add AnalyticsService"
```

---

## Task 4: `bar-chart` component

Reusable horizontal bar list (used by top-skills, skill-gap, remote-mix). Input: a list of `{ label, value, pct, note? }`.

**Files:** Create `frontend/src/app/pages/analytics/components/bar-chart/bar-chart.component.ts`/`.html`/`.scss` + `.spec.ts`.

- [ ] **Step 1: Write the failing test** (`bar-chart.component.spec.ts`)

```typescript
import { TestBed } from '@angular/core/testing';
import { BarChartComponent } from './bar-chart.component';

describe('BarChartComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [BarChartComponent] }).compileComponents();
  });

  function mount(rows: unknown[]) {
    const fixture = TestBed.createComponent(BarChartComponent);
    fixture.componentRef.setInput('rows', rows);
    fixture.detectChanges();
    return fixture;
  }

  it('renders one bar per row', () => {
    const fixture = mount([
      { label: 'python', value: 3, pct: 75 },
      { label: 'react', value: 1, pct: 25 },
    ]);
    expect(fixture.nativeElement.querySelectorAll('.bar-row').length).toBe(2);
  });

  it('sets bar width from pct', () => {
    const fixture = mount([{ label: 'python', value: 3, pct: 50 }]);
    const fill = fixture.nativeElement.querySelector('.bar-fill') as HTMLElement;
    expect(fill.style.width).toBe('50%');
  });

  it('shows empty state when no rows', () => {
    const fixture = mount([]);
    expect(fixture.nativeElement.querySelector('.bar-empty')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `bar-chart.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export interface BarRow {
  label: string;
  value: number;
  pct: number;
  note?: string;
}

@Component({
  selector: 'app-bar-chart',
  standalone: true,
  templateUrl: './bar-chart.component.html',
  styleUrl: './bar-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BarChartComponent {
  rows = input.required<BarRow[]>();
  emptyText = input<string>('No data yet.');
}
```

- [ ] **Step 4: Template** `bar-chart.component.html`:

```html
@if (rows().length === 0) {
  <p class="bar-empty">{{ emptyText() }}</p>
} @else {
  <ul class="bar-list">
    @for (row of rows(); track row.label) {
      <li class="bar-row">
        <span class="bar-label" [title]="row.label">{{ row.label }}</span>
        <span class="bar-track">
          <span class="bar-fill" [style.width.%]="row.pct"></span>
        </span>
        <span class="bar-value">{{ row.value }}@if (row.note) { <span class="bar-note">{{ row.note }}</span> }</span>
      </li>
    }
  </ul>
}
```

- [ ] **Step 5: Styles** `bar-chart.component.scss`:

```scss
.bar-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.4rem; }
.bar-row { display: grid; grid-template-columns: 9rem 1fr auto; align-items: center; gap: 0.6rem; font-size: 0.85rem; }
.bar-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { background: var(--surface-hover, #f1f5f9); border-radius: 999px; height: 0.6rem; overflow: hidden; }
.bar-fill { display: block; height: 100%; background: var(--accent, #4f46e5); border-radius: 999px; transition: width 0.3s; }
.bar-value { font-variant-numeric: tabular-nums; color: var(--muted, #64748b); }
.bar-note { margin-left: 0.35rem; }
.bar-empty { color: var(--muted, #64748b); font-size: 0.85rem; }
```

- [ ] **Step 6: Run → PASS.** Commit:

```bash
git add frontend/src/app/pages/analytics/components/bar-chart/
git commit -m "feat(analytics-fe): add bar-chart component"
```

---

## Task 5: `trend-line` component

Inline SVG polyline for postings-per-week.

**Files:** Create `frontend/src/app/pages/analytics/components/trend-line/trend-line.component.ts`/`.html`/`.scss` + `.spec.ts`.

- [ ] **Step 1: Write the failing test**

```typescript
import { TestBed } from '@angular/core/testing';
import { TrendLineComponent } from './trend-line.component';

describe('TrendLineComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [TrendLineComponent] }).compileComponents();
  });

  function mount(points: unknown[]) {
    const fixture = TestBed.createComponent(TrendLineComponent);
    fixture.componentRef.setInput('points', points);
    fixture.detectChanges();
    return fixture;
  }

  it('renders a polyline when 2+ points', () => {
    const fixture = mount([{ week: '2026-W18', count: 2 }, { week: '2026-W19', count: 5 }]);
    expect(fixture.nativeElement.querySelector('polyline')).not.toBeNull();
  });

  it('shows empty state with no points', () => {
    const fixture = mount([]);
    expect(fixture.nativeElement.querySelector('.trend-empty')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `trend-line.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TrendPoint } from '../../models/market-intel.model';

const W = 320;
const H = 80;
const PAD = 4;

@Component({
  selector: 'app-trend-line',
  standalone: true,
  templateUrl: './trend-line.component.html',
  styleUrl: './trend-line.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrendLineComponent {
  points = input.required<TrendPoint[]>();

  readonly viewBox = `0 0 ${W} ${H}`;

  polyline = computed(() => {
    const pts = this.points();
    if (pts.length < 2) return '';
    const max = Math.max(...pts.map((p) => p.count), 1);
    const stepX = (W - 2 * PAD) / (pts.length - 1);
    return pts
      .map((p, i) => {
        const x = PAD + i * stepX;
        const y = H - PAD - (p.count / max) * (H - 2 * PAD);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  });
}
```

- [ ] **Step 4: Template** `trend-line.component.html`:

```html
@if (points().length < 2) {
  <p class="trend-empty">Not enough data for a trend yet.</p>
} @else {
  <svg class="trend-svg" [attr.viewBox]="viewBox" preserveAspectRatio="none" role="img" aria-label="Postings per week">
    <polyline [attr.points]="polyline()" fill="none" stroke="var(--accent, #4f46e5)" stroke-width="2" />
  </svg>
}
```

- [ ] **Step 5: Styles** `trend-line.component.scss`:

```scss
.trend-svg { width: 100%; height: 80px; display: block; }
.trend-empty { color: var(--muted, #64748b); font-size: 0.85rem; }
```

- [ ] **Step 6: Run → PASS.** Commit:

```bash
git add frontend/src/app/pages/analytics/components/trend-line/
git commit -m "feat(analytics-fe): add trend-line component"
```

---

## Task 6: `funnel-chart` component

Stage bars with reached counts, conversion %, and median time-in-stage; plus a rejected note.

**Files:** Create `frontend/src/app/pages/analytics/components/funnel-chart/funnel-chart.component.ts`/`.html`/`.scss` + `.spec.ts`.

- [ ] **Step 1: Write the failing test**

```typescript
import { TestBed } from '@angular/core/testing';
import { FunnelChartComponent } from './funnel-chart.component';

const METRICS = {
  stages: [
    { stage: 'saved', reached: 4, conversion_from_prev: null, median_days_in_stage: 2, current: 1 },
    { stage: 'applied', reached: 3, conversion_from_prev: 0.75, median_days_in_stage: 5, current: 1 },
    { stage: 'interviewing', reached: 1, conversion_from_prev: 0.33, median_days_in_stage: null, current: 1 },
    { stage: 'offered', reached: 0, conversion_from_prev: 0, median_days_in_stage: null, current: 0 },
    { stage: 'accepted', reached: 0, conversion_from_prev: null, median_days_in_stage: null, current: 0 },
  ],
  rejected: 1, current_rejected: 1, total_applications: 4,
};

describe('FunnelChartComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [FunnelChartComponent] }).compileComponents();
  });

  function mount(metrics: unknown) {
    const fixture = TestBed.createComponent(FunnelChartComponent);
    fixture.componentRef.setInput('metrics', metrics);
    fixture.detectChanges();
    return fixture;
  }

  it('renders a row per stage', () => {
    const fixture = mount(METRICS);
    expect(fixture.nativeElement.querySelectorAll('.funnel-stage').length).toBe(5);
  });

  it('shows conversion % where present', () => {
    const fixture = mount(METRICS);
    expect(fixture.nativeElement.textContent).toContain('75%');
  });

  it('shows rejected count', () => {
    const fixture = mount(METRICS);
    expect(fixture.nativeElement.textContent).toContain('1');
  });

  it('empty state when no applications', () => {
    const fixture = mount({ stages: [], rejected: 0, current_rejected: 0, total_applications: 0 });
    expect(fixture.nativeElement.querySelector('.funnel-empty')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `funnel-chart.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { FunnelMetrics } from '../../models/funnel-metrics.model';

@Component({
  selector: 'app-funnel-chart',
  standalone: true,
  templateUrl: './funnel-chart.component.html',
  styleUrl: './funnel-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FunnelChartComponent {
  metrics = input.required<FunnelMetrics>();

  // Bar width relative to the first stage's reached count (the widest).
  maxReached = computed(() => Math.max(1, ...this.metrics().stages.map((s) => s.reached)));

  width(reached: number): number {
    return Math.round((reached / this.maxReached()) * 100);
  }

  pct(conversion: number | null): string | null {
    return conversion === null ? null : `${Math.round(conversion * 100)}%`;
  }
}
```

- [ ] **Step 4: Template** `funnel-chart.component.html`:

```html
@if (metrics().total_applications === 0) {
  <p class="funnel-empty">Track applications to see your funnel.</p>
} @else {
  <ul class="funnel-list">
    @for (s of metrics().stages; track s.stage) {
      <li class="funnel-stage">
        <div class="funnel-head">
          <span class="funnel-name">{{ s.stage }}</span>
          <span class="funnel-reached">{{ s.reached }}</span>
        </div>
        <span class="funnel-track"><span class="funnel-fill" [style.width.%]="width(s.reached)"></span></span>
        <div class="funnel-meta">
          @if (pct(s.conversion_from_prev); as c) { <span class="funnel-conv">{{ c }} from prev</span> }
          @if (s.median_days_in_stage !== null) { <span class="funnel-time">~{{ s.median_days_in_stage }}d in stage</span> }
        </div>
      </li>
    }
  </ul>
  <p class="funnel-rejected">Rejected: {{ metrics().rejected }} total ({{ metrics().current_rejected }} currently)</p>
}
```

- [ ] **Step 5: Styles** `funnel-chart.component.scss`:

```scss
.funnel-list { list-style: none; margin: 0 0 0.75rem; padding: 0; display: flex; flex-direction: column; gap: 0.7rem; }
.funnel-head { display: flex; justify-content: space-between; font-size: 0.85rem; }
.funnel-name { text-transform: capitalize; font-weight: 600; }
.funnel-reached { font-variant-numeric: tabular-nums; }
.funnel-track { display: block; background: var(--surface-hover, #f1f5f9); border-radius: 6px; height: 0.7rem; margin: 0.25rem 0; overflow: hidden; }
.funnel-fill { display: block; height: 100%; background: var(--accent, #4f46e5); border-radius: 6px; transition: width 0.3s; }
.funnel-meta { display: flex; gap: 0.8rem; font-size: 0.75rem; color: var(--muted, #64748b); }
.funnel-rejected { font-size: 0.8rem; color: var(--muted, #64748b); }
.funnel-empty { color: var(--muted, #64748b); font-size: 0.85rem; }
```

- [ ] **Step 6: Run → PASS.** Commit:

```bash
git add frontend/src/app/pages/analytics/components/funnel-chart/
git commit -m "feat(analytics-fe): add funnel-chart component"
```

---

## Task 7: `salary-band` component

Market min/median/max bar overlaid with the user's target band.

**Files:** Create `frontend/src/app/pages/analytics/components/salary-band/salary-band.component.ts`/`.html`/`.scss` + `.spec.ts`.

- [ ] **Step 1: Write the failing test**

```typescript
import { TestBed } from '@angular/core/testing';
import { SalaryBandComponent } from './salary-band.component';

describe('SalaryBandComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [SalaryBandComponent] }).compileComponents();
  });

  function mount(target: unknown) {
    const fixture = TestBed.createComponent(SalaryBandComponent);
    fixture.componentRef.setInput('target', target);
    fixture.detectChanges();
    return fixture;
  }

  it('shows insufficient-data state', () => {
    const fixture = mount({ insufficient_data: true, currency: null, p25_annual: null,
      median_annual: null, p75_annual: null, sample_size: 0 });
    expect(fixture.nativeElement.querySelector('.band-insufficient')).not.toBeNull();
  });

  it('renders the band with median when sufficient', () => {
    const fixture = mount({ insufficient_data: false, currency: 'USD', p25_annual: 90000,
      median_annual: 110000, p75_annual: 130000, sample_size: 12 });
    expect(fixture.nativeElement.querySelector('.band-fill')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('110,000');
  });
});
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `salary-band.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TargetSalary } from '../../models/target-salary.model';

@Component({
  selector: 'app-salary-band',
  standalone: true,
  templateUrl: './salary-band.component.html',
  styleUrl: './salary-band.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SalaryBandComponent {
  target = input.required<TargetSalary>();

  // p25→p75 band positioned within a p25*0.8 .. p75*1.2 visual scale.
  band = computed(() => {
    const t = this.target();
    if (t.insufficient_data || t.p25_annual === null || t.p75_annual === null) return null;
    const lo = t.p25_annual * 0.8;
    const hi = t.p75_annual * 1.2;
    const span = Math.max(1, hi - lo);
    const left = ((t.p25_annual - lo) / span) * 100;
    const width = ((t.p75_annual - t.p25_annual) / span) * 100;
    const median = t.median_annual === null ? null : ((t.median_annual - lo) / span) * 100;
    return { left, width, median };
  });

  fmt(v: number | null): string {
    return v === null ? '—' : v.toLocaleString('en-US');
  }
}
```

- [ ] **Step 4: Template** `salary-band.component.html`:

```html
@if (target().insufficient_data) {
  <p class="band-insufficient">
    Not enough salary data for your profile yet ({{ target().sample_size }} matches).
  </p>
} @else if (band(); as b) {
  <div class="band-numbers">
    <span>{{ target().currency }} {{ fmt(target().p25_annual) }}</span>
    <strong>{{ fmt(target().median_annual) }}</strong>
    <span>{{ fmt(target().p75_annual) }}</span>
  </div>
  <div class="band-track">
    <span class="band-fill" [style.left.%]="b.left" [style.width.%]="b.width"></span>
    @if (b.median !== null) { <span class="band-median" [style.left.%]="b.median"></span> }
  </div>
  <p class="band-sample">Based on {{ target().sample_size }} profile-similar roles.</p>
}
```

- [ ] **Step 5: Styles** `salary-band.component.scss`:

```scss
.band-numbers { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.35rem; }
.band-numbers strong { font-size: 1.1rem; }
.band-track { position: relative; height: 0.8rem; background: var(--surface-hover, #f1f5f9); border-radius: 999px; }
.band-fill { position: absolute; top: 0; height: 100%; background: var(--accent-soft, #c7d2fe); border-radius: 999px; }
.band-median { position: absolute; top: -2px; width: 2px; height: calc(100% + 4px); background: var(--accent, #4f46e5); }
.band-sample { font-size: 0.75rem; color: var(--muted, #64748b); margin-top: 0.35rem; }
.band-insufficient { color: var(--muted, #64748b); font-size: 0.85rem; }
```

- [ ] **Step 6: Run → PASS.** Commit:

```bash
git add frontend/src/app/pages/analytics/components/salary-band/
git commit -m "feat(analytics-fe): add salary-band component"
```

---

## Task 8: Analytics page component

Loads the four results independently into signals; each section shows loading/error/empty; composes the four charts into cards.

**Files:** Create `frontend/src/app/pages/analytics/analytics.component.ts`/`.html`/`.scss` + `.spec.ts`.

- [ ] **Step 1: Write the failing test** (`analytics.component.spec.ts`)

```typescript
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { AnalyticsComponent } from './analytics.component';
import { AnalyticsService } from '../../core/services/analytics.service';

function makeService(over: Partial<Record<string, unknown>> = {}) {
  return {
    funnel: () => of({ stages: [], rejected: 0, current_rejected: 0, total_applications: 0 }),
    market: () => of({ top_skills: [{ skill: 'python', count: 3, pct: 75 }], remote_mix: { remote: 2 },
      posting_trend: [], salary_distribution: { currency: 'USD', min_annual: 90000, median_annual: 110000,
      max_annual: 130000, parsed_count: 5, unparsed_count: 1, other_currency_count: 0, disclosed_pct: 80 } }),
    skillGap: () => of({ has_profile: true, missing: [{ skill: 'rust', count: 2, pct: 40 }] }),
    targetSalary: () => of({ insufficient_data: true, currency: null, p25_annual: null,
      median_annual: null, p75_annual: null, sample_size: 0 }),
    ...over,
  };
}

describe('AnalyticsComponent', () => {
  function mount(service: unknown) {
    TestBed.configureTestingModule({
      imports: [AnalyticsComponent],
      providers: [{ provide: AnalyticsService, useValue: service }],
    });
    const fixture = TestBed.createComponent(AnalyticsComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the four section cards on success', () => {
    const fixture = mount(makeService());
    expect(fixture.nativeElement.querySelectorAll('.analytics-card').length).toBe(4);
  });

  it('renders a top skill from market', () => {
    const fixture = mount(makeService());
    expect(fixture.nativeElement.textContent).toContain('python');
  });

  it('shows a section error when an endpoint fails', () => {
    const fixture = mount(makeService({ funnel: () => throwError(() => new Error('boom')) }));
    expect(fixture.nativeElement.querySelector('.section-error')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `analytics.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AnalyticsService } from '../../core/services/analytics.service';
import { FunnelMetrics } from './models/funnel-metrics.model';
import { MarketIntel } from './models/market-intel.model';
import { SkillGap } from './models/skill-gap.model';
import { TargetSalary } from './models/target-salary.model';
import { BarChartComponent, BarRow } from './components/bar-chart/bar-chart.component';
import { FunnelChartComponent } from './components/funnel-chart/funnel-chart.component';
import { TrendLineComponent } from './components/trend-line/trend-line.component';
import { SalaryBandComponent } from './components/salary-band/salary-band.component';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [BarChartComponent, FunnelChartComponent, TrendLineComponent, SalaryBandComponent],
  templateUrl: './analytics.component.html',
  styleUrl: './analytics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalyticsComponent implements OnInit {
  private analytics = inject(AnalyticsService);
  private destroyRef = inject(DestroyRef);

  funnel = signal<FunnelMetrics | null>(null);
  funnelError = signal(false);

  market = signal<MarketIntel | null>(null);
  marketError = signal(false);

  skillGap = signal<SkillGap | null>(null);
  skillGapError = signal(false);

  targetSalary = signal<TargetSalary | null>(null);
  targetSalaryError = signal(false);

  ngOnInit(): void {
    this.analytics.funnel().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (v) => this.funnel.set(v), error: () => this.funnelError.set(true),
    });
    this.analytics.market().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (v) => this.market.set(v), error: () => this.marketError.set(true),
    });
    this.analytics.skillGap().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (v) => this.skillGap.set(v), error: () => this.skillGapError.set(true),
    });
    this.analytics.targetSalary().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (v) => this.targetSalary.set(v), error: () => this.targetSalaryError.set(true),
    });
  }

  skillRows(m: MarketIntel): BarRow[] {
    return m.top_skills.map((s) => ({ label: s.skill, value: s.count, pct: s.pct, note: `${s.pct}%` }));
  }

  gapRows(g: SkillGap): BarRow[] {
    return g.missing.map((s) => ({ label: s.skill, value: s.count, pct: s.pct, note: `in ${s.pct}%` }));
  }

  remoteRows(m: MarketIntel): BarRow[] {
    const total = Object.values(m.remote_mix).reduce((a, b) => a + b, 0) || 1;
    return Object.entries(m.remote_mix).map(([k, v]) => ({
      label: k, value: v, pct: Math.round((v / total) * 100), note: `${Math.round((v / total) * 100)}%`,
    }));
  }
}
```

- [ ] **Step 4: Template** `analytics.component.html`:

```html
<div class="analytics-page">
  <h1 class="analytics-title">Analytics</h1>
  <div class="analytics-grid">

    <section class="analytics-card">
      <h2 class="card-title">Your funnel</h2>
      @if (funnelError()) { <p class="section-error">Couldn't load the funnel.</p> }
      @else if (funnel(); as f) { <app-funnel-chart [metrics]="f" /> }
      @else { <p class="section-loading">Loading…</p> }
    </section>

    <section class="analytics-card">
      <h2 class="card-title">Target salary</h2>
      @if (targetSalaryError()) { <p class="section-error">Couldn't load target salary.</p> }
      @else if (targetSalary(); as t) { <app-salary-band [target]="t" /> }
      @else { <p class="section-loading">Loading…</p> }
    </section>

    <section class="analytics-card">
      <h2 class="card-title">Market</h2>
      @if (marketError()) { <p class="section-error">Couldn't load market intel.</p> }
      @else if (market(); as m) {
        <h3 class="sub">Top skills in demand</h3>
        <app-bar-chart [rows]="skillRows(m)" emptyText="No skills in the corpus yet." />
        <h3 class="sub">Remote vs on-site</h3>
        <app-bar-chart [rows]="remoteRows(m)" emptyText="No modality data." />
        <h3 class="sub">Postings per week</h3>
        <app-trend-line [points]="m.posting_trend" />
        <h3 class="sub">Salary range
          @if (m.salary_distribution.currency) { ({{ m.salary_distribution.currency }}, {{ m.salary_distribution.disclosed_pct }}% disclosed) }
        </h3>
        @if (m.salary_distribution.median_annual !== null) {
          <p class="salary-line">{{ m.salary_distribution.min_annual }} – <strong>{{ m.salary_distribution.median_annual }}</strong> – {{ m.salary_distribution.max_annual }}</p>
        } @else { <p class="section-loading">No parseable salaries.</p> }
      }
      @else { <p class="section-loading">Loading…</p> }
    </section>

    <section class="analytics-card">
      <h2 class="card-title">Skill gap</h2>
      @if (skillGapError()) { <p class="section-error">Couldn't load skill gap.</p> }
      @else if (skillGap(); as g) {
        @if (g.has_profile) { <app-bar-chart [rows]="gapRows(g)" emptyText="No gaps — you cover the market." /> }
        @else { <p class="section-empty">Upload a CV to see your skill gap.</p> }
      }
      @else { <p class="section-loading">Loading…</p> }
    </section>

  </div>
</div>
```

- [ ] **Step 5: Styles** `analytics.component.scss`:

```scss
.analytics-page { padding: 1.25rem; }
.analytics-title { font-size: 1.4rem; margin: 0 0 1rem; }
.analytics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr)); gap: 1rem; }
.analytics-card { border: 1px solid var(--border, #e2e8f0); border-radius: 10px; padding: 1rem; background: var(--surface, #fff); }
.card-title { font-size: 1rem; margin: 0 0 0.75rem; }
.sub { font-size: 0.8rem; color: var(--muted, #64748b); margin: 0.9rem 0 0.4rem; text-transform: uppercase; letter-spacing: 0.03em; }
.salary-line { font-size: 0.9rem; }
.section-loading, .section-empty { color: var(--muted, #64748b); font-size: 0.85rem; }
.section-error { color: var(--danger, #dc2626); font-size: 0.85rem; }
```

- [ ] **Step 6: Run → PASS.** Commit:

```bash
git add frontend/src/app/pages/analytics/analytics.component.ts frontend/src/app/pages/analytics/analytics.component.html frontend/src/app/pages/analytics/analytics.component.scss frontend/src/app/pages/analytics/analytics.component.spec.ts
git commit -m "feat(analytics-fe): add analytics page component"
```

---

## Task 9: Route + sidebar nav link

**Files:** Modify `frontend/src/app/app.routes.ts`, `frontend/src/app/pages/dashboard/dashboard.component.html`.

- [ ] **Step 1: Add the child route** — in `app.routes.ts`, inside the `dashboard` `children` array (after `tracking`):

```typescript
      { path: 'analytics', loadComponent: () => import('./pages/analytics/analytics.component').then(m => m.AnalyticsComponent) },
```

- [ ] **Step 2: Add the nav link** — in `dashboard.component.html`, after the `tracking` `<a>` block and before the `<div class="nav-section-label">Admin</div>`:

```html
      <a routerLink="analytics" routerLinkActive="active">
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="20" x2="18" y2="10"/>
            <line x1="12" y1="20" x2="12" y2="4"/>
            <line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
        </span>
        <span>Analytics</span>
      </a>
```

- [ ] **Step 3: Verify build + tests**

Run: `cd frontend && npm run build`
Expected: build succeeds.

Run: `cd frontend && npx ng test --no-watch`
Expected: PASS (all suites green).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/app.routes.ts frontend/src/app/pages/dashboard/dashboard.component.html
git commit -m "feat(analytics-fe): add analytics route + sidebar nav link"
```

---

## Task 10: Final verification

- [ ] **Step 1: Frontend tests** — `cd frontend && npx ng test --no-watch` → PASS (AnalyticsService 4, bar-chart 3, trend-line 2, funnel-chart 4, salary-band 2, analytics page 3, + pre-existing).
- [ ] **Step 2: Frontend build** — `cd frontend && npm run build` → succeeds.
- [ ] **Step 3: Backend** — `cd backend && uv run python -m pytest -q` → PASS (the `current_rejected` change). `cd backend && uv run python -m ruff check src/hiresense/analytics/domain/funnel_service.py` → clean.
- [ ] **Step 4: Manual smoke (optional)** — with backend + `npm start`, open `/dashboard/analytics`: four cards render; funnel shows stages/conversion/time; market shows skills/remote/trend/salary; skill-gap lists missing skills (or "upload a CV"); target salary shows a band or insufficient-data.

---

## Self-Review notes

- **Spec coverage (§Architecture.3):** `/dashboard/analytics` route + nav (T9) ✓; `AnalyticsService` four methods (T3) ✓; models mirroring backend incl. `disclosed_pct`/`current_rejected` (T2, T1) ✓; hand-rolled CSS/SVG charts — bar-chart, funnel-chart, trend-line, salary-band (T4–T7) ✓; four section cards with per-section loading/error/empty (T8) ✓; "upload a CV" skill-gap neutral + insufficient-data salary states (T7, T8) ✓.
- **Carried Phase-2 note resolved:** `current_rejected` added to the funnel (T1) so the funnel card reconciles current-status counts.
- **Type/name consistency:** TS model field names match the backend JSON exactly (snake_case preserved — no camelCase remap, so `response_model` JSON binds directly); `BarRow` reused across skill/gap/remote; chart component `input.required` names (`rows`, `points`, `metrics`, `target`) match the page bindings.
- **No placeholders:** every step has complete code; component tests assert real DOM.
- **Out of scope:** list-card analytics, CSV export, interactive/tooltip charts (hand-rolled only), seniority mix.

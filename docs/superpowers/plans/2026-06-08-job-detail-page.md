# Job Detail Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a job a dedicated, complete `/dashboard/job/:id` page (header + description + auto-loaded deep analysis + actions), slim the modal panel by moving only the deep-analysis block out of it, and extract a shared job-description component.

**Architecture:** Frontend-only. Reuse the existing `getJob` / `getJobAnalysis` (cache-backed) endpoints, the `DeepAnalysisComponent`, `FeedbackControlsComponent`, the `parseJobDescription` lib, and the `scoreColor`/`formatScorePercent` utils. New shared `JobDescriptionComponent` is consumed by both the slimmed panel and the new page.

**Tech Stack:** Angular 21 standalone + signals, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-08-job-detail-page-design.md`

**Conventions:**
- Frontend tests from `frontend/`: `npm test -- --watch=false --include "<glob>"`. Lint: `npx ng lint` (CI gate; `npm test`/`build` skip it).
- Commit directly to `main` (user consented). Do NOT push. Dev server already running — don't start another.
- Conventional Commits, scope `ingestion`.

---

## Task 1: Shared `JobDescriptionComponent` + slim the panel

Extract description rendering into a reusable component, then refactor `JobDetailPanelComponent` to (a) use it and (b) drop the deep-analysis block in favour of a "View full analysis →" link.

**Files:**
- Create: `frontend/src/app/pages/ingestion/components/job-description/job-description.component.ts`
- Create: `frontend/src/app/pages/ingestion/components/job-description/job-description.component.html`
- Create: `frontend/src/app/pages/ingestion/components/job-description/job-description.component.scss`
- Create: `frontend/src/app/pages/ingestion/components/job-description/job-description.component.spec.ts`
- Modify: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.ts`
- Modify: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.html`
- Modify: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.spec.ts`

- [ ] **Step 1: Write the failing spec for the shared component**

Create `…/job-description/job-description.component.spec.ts`:
```typescript
import { TestBed } from '@angular/core/testing';
import { JobDescriptionComponent } from './job-description.component';

function mount(description: string) {
  TestBed.configureTestingModule({ imports: [JobDescriptionComponent] });
  const fixture = TestBed.createComponent(JobDescriptionComponent);
  fixture.componentRef.setInput('description', description);
  fixture.detectChanges();
  return fixture;
}

describe('JobDescriptionComponent', () => {
  it('renders structured sections when the description has *Headers*', () => {
    const fixture = mount('Intro line\n*Stack*:\nPython, Django');
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Stack');
    expect(text).toContain('Python, Django');
    expect(fixture.nativeElement.querySelectorAll('.jd-section').length).toBeGreaterThan(0);
  });

  it('falls back to raw text when there are no sections', () => {
    const fixture = mount('Just a plain description with no headers.');
    expect(fixture.nativeElement.querySelector('.jd-raw')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('plain description');
  });
});
```

- [ ] **Step 2: Run it to verify failure**

Run: `npm test -- --watch=false --include "**/job-description.component.spec.ts"` (from `frontend/`)
Expected: FAIL — component doesn't exist.

- [ ] **Step 3: Create the component**

Create `…/job-description/job-description.component.ts`:
```typescript
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { parseJobDescription } from '../../lib/parse-job-description';

@Component({
  selector: 'app-job-description',
  standalone: true,
  imports: [],
  templateUrl: './job-description.component.html',
  styleUrl: './job-description.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JobDescriptionComponent {
  description = input.required<string>();

  parsed = computed(() => parseJobDescription(this.description() ?? ''));
  hasSections = computed(() => this.parsed().sections.length > 0);
}
```

- [ ] **Step 4: Create the template**

Create `…/job-description/job-description.component.html`:
```html
@if (hasSections()) {
  @if (parsed().intro) {
    <p class="jd-prose jd-intro">{{ parsed().intro }}</p>
  }
  @for (section of parsed().sections; track section.title) {
    <div class="jd-section" [attr.data-emphasis]="section.emphasis">
      <span class="jd-section-title">{{ section.title }}</span>
      <p class="jd-prose">{{ section.body }}</p>
    </div>
  }
} @else {
  <p class="jd-prose jd-raw">{{ description() }}</p>
}
```

- [ ] **Step 5: Create the styles**

Create `…/job-description/job-description.component.scss`:
```scss
.jd-prose {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--text-secondary);
  white-space: pre-wrap;
}
.jd-intro { margin-bottom: 0.75rem; }
.jd-section {
  margin-top: 0.85rem;
  padding: 0.75rem 0.9rem;
  background: var(--bg-inset);
  border: 1px solid var(--border-subtle);
  border-left: 3px solid var(--border-default);
  border-radius: var(--radius-md);

  &[data-emphasis='compensation'] { border-left-color: var(--success); }
  &[data-emphasis='apply'] { border-left-color: var(--accent); }
  &[data-emphasis='stack'] { border-left-color: var(--info-text); }
  &[data-emphasis='role'] { border-left-color: var(--warning); }
}
.jd-section-title {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}
```

- [ ] **Step 6: Run the spec to verify it passes**

Run: `npm test -- --watch=false --include "**/job-description.component.spec.ts"`
Expected: PASS (2 tests).

- [ ] **Step 7: Refactor the panel component TS**

In `job-detail-panel.component.ts`:

(a) Swap the `DeepAnalysisComponent` import for the new component. Change:
```typescript
import { DeepAnalysisComponent } from '../deep-analysis/deep-analysis.component';
import { FeedbackControlsComponent } from '../feedback-controls/feedback-controls.component';
```
to:
```typescript
import { JobDescriptionComponent } from '../job-description/job-description.component';
import { FeedbackControlsComponent } from '../feedback-controls/feedback-controls.component';
```
And in the `@Component` `imports` array, replace `DeepAnalysisComponent` with `JobDescriptionComponent`:
```typescript
  imports: [DatePipe, JobDescriptionComponent, FeedbackControlsComponent],
```

(b) Remove the deep-analysis state and methods. Delete these members entirely:
- the `analysis = computed(...)` block (the one using `getCachedAnalysis`),
- `analysisExpanded`, `analysisLoading`, `analysisError` signals,
- `toggleDeepAnalysis()`, `loadAnalysis()`, `retryAnalysis()` methods,
- the `hasStructuredSections` computed.

Keep `parsedDescription` (still used by `compensationHighlight`), `compensationHighlight`, the `pillScore`/`scorePercent` computeds, `parsedDescription`, and all the output/track/escape handlers.

(c) The component still injects `Router`. Add a navigation method (place it next to `goToMatching`):
```typescript
  goToFullAnalysis(): void {
    this.router.navigate(['/dashboard/job', this.job().id]);
    this.closed.emit();
  }
```
The `IngestionService` import/inject is now only needed if something else uses it — check: after removing `analysis`/`loadAnalysis`, `ingestionService` is unused. Remove the `IngestionService` import and the `private ingestionService = inject(IngestionService);` line. (Leave `destroyRef` only if still used; after removing `loadAnalysis` it is unused — remove the `destroyRef` field and its import too if nothing else references it. Verify by searching the file for `destroyRef` / `ingestionService` before deleting.)

- [ ] **Step 8: Refactor the panel template**

In `job-detail-panel.component.html`:

(a) Replace the entire **Deep analysis** block (the `<div class="panel-section section-card" [attr.data-emphasis]="'role'">…</div>` containing the `deep-toggle` button and the `@if (analysisExpanded())` tree) with:
```html
      <!-- Full analysis lives on the dedicated job page -->
      <div class="panel-section">
        <button type="button" class="deep-toggle" (click)="goToFullAnalysis()">
          <span class="section-label">Full analysis</span>
          <span class="deep-toggle-action">View pros, cons &amp; breakdown →</span>
        </button>
      </div>
```

(b) Replace the entire **Description** block (the `@if (hasStructuredSections()) { … } @else { … }` tree, including its surrounding `panel-section`s) with:
```html
      <!-- Description -->
      <div class="panel-section">
        <span class="section-label">Description</span>
        <app-job-description [description]="job().description" />
      </div>
```

- [ ] **Step 9: Update the panel spec**

In `job-detail-panel.component.spec.ts` (it uses a `mount(job?, inputs?)` helper and a `navigate = vi.fn()` Router mock):

(a) **Delete the two deep-analysis tests entirely** — `it('loads deep analysis on first expand and renders the success state', …)` and `it('surfaces the deep analysis error state and retries', …)`. Their behaviour no longer exists in the panel.

(b) Remove the now-unused analysis mock plumbing:
- delete the `let getJobAnalysis: …;` and `let getCachedAnalysis: …;` declarations,
- delete the `getJobAnalysis = vi.fn()…;` and `getCachedAnalysis = vi.fn()…;` assignments in `beforeEach`,
- delete the entire `{ provide: IngestionService, useValue: { getJobAnalysis, getCachedAnalysis } }` provider (the slimmed panel no longer injects `IngestionService`),
- remove the now-unused `IngestionService` import and the unused `JobAnalysis` import and the `ANALYSIS` const if nothing else references them (the two deleted tests were their only users — verify with a search before deleting).

Keep the `Router` provider (`{ provide: Router, useValue: { navigate } }`) — the panel still injects `Router`.

(c) Add this test (the new template renders `<button class="deep-toggle" (click)="goToFullAnalysis()">` whose label contains "Full analysis"):
```typescript
  it('links to the full analysis page instead of expanding analysis inline', () => {
    const fixture = mount();
    let closed = false;
    fixture.componentInstance.closed.subscribe(() => (closed = true));

    expect(fixture.nativeElement.querySelector('app-deep-analysis')).toBeNull();
    const link = Array.from(
      fixture.nativeElement.querySelectorAll('button.deep-toggle') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.includes('Full analysis'))!;
    link.click();

    expect(navigate).toHaveBeenCalledWith(['/dashboard/job', 'job-1']);
    expect(closed).toBe(true);
  });
```

- [ ] **Step 10: Run the panel + description specs and lint**

Run: `npm test -- --watch=false --include "**/job-detail-panel.component.spec.ts" --include "**/job-description.component.spec.ts"` then `npx ng lint` (from `frontend/`)
Expected: all specs PASS; lint clean.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/app/pages/ingestion/components/job-description/ frontend/src/app/pages/ingestion/components/job-detail-panel/
git commit -m "refactor(ingestion): extract shared job-description, slim panel to link to full analysis"
```

---

## Task 2: `JobDetailComponent` page + route

**Files:**
- Create: `frontend/src/app/pages/job/job.component.ts`
- Create: `frontend/src/app/pages/job/job.component.html`
- Create: `frontend/src/app/pages/job/job.component.scss`
- Create: `frontend/src/app/pages/job/job.component.spec.ts`
- Modify: `frontend/src/app/app.routes.ts`

- [ ] **Step 1: Write the failing spec**

Create `frontend/src/app/pages/job/job.component.spec.ts`:
```typescript
import { TestBed } from '@angular/core/testing';
import { provideRouter, ActivatedRoute, convertToParamMap } from '@angular/router';
import { of, throwError } from 'rxjs';
import { JobDetailComponent } from './job.component';
import { IngestionService } from '../../core/services/ingestion.service';
import { ApplicationsService } from '../../core/services/applications.service';

function job(over: Record<string, unknown> = {}) {
  return {
    id: 'j1', title: 'Backend Engineer', company: 'Acme', description: 'Plain description.',
    skills: ['python'], location: 'Remote', salary_range: null, source: 'remotive',
    source_type: 'api', platform: null, categories: [], department: null,
    url: 'https://e.com/1', posted_date: null, match_score: 0.82, llm_score: null,
    verdict: 'strong', reasons: ['Good skill overlap'], dealbreakers: [], status: 'open', ...over,
  };
}

const analysis = {
  job_id: 'j1', overall_score: 0.8, verdict: 'strong', dimensions: [],
  matched_skills: ['python'], missing_skills: [], pros: ['Remote'], cons: ['Low pay'],
  recommendations: [], narrative: 'Solid fit.',
};

function mount(over: Partial<Record<string, unknown>> = {}, id = 'j1') {
  const ingestion = {
    getJob: () => of(job()),
    getCachedAnalysis: () => undefined,
    getJobAnalysis: () => of(analysis),
    trackedJobIds: () => new Set<string>(),
    markTracked: () => {},
    ...over,
  };
  TestBed.configureTestingModule({
    imports: [JobDetailComponent],
    providers: [
      provideRouter([]),
      { provide: IngestionService, useValue: ingestion },
      { provide: ApplicationsService, useValue: { createFromJob: () => of({}) } },
      { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id }) } } },
    ],
  });
  const fixture = TestBed.createComponent(JobDetailComponent);
  fixture.detectChanges();
  return fixture;
}

describe('JobDetailComponent', () => {
  it('renders the job header with a company link and the analysis', () => {
    const fixture = mount();
    expect(fixture.nativeElement.textContent).toContain('Backend Engineer');
    const companyLink = fixture.nativeElement.querySelector('a.job-company') as HTMLAnchorElement;
    expect(companyLink?.getAttribute('href')).toBe('/dashboard/company/Acme');
    expect(fixture.nativeElement.querySelector('app-deep-analysis')).not.toBeNull();
  });

  it('shows the job error state when the fetch fails', () => {
    const fixture = mount({ getJob: () => throwError(() => new Error('boom')) });
    expect(fixture.nativeElement.querySelector('.job-state-error')).not.toBeNull();
  });

  it('shows the analysis error state when analysis fails', () => {
    const fixture = mount({ getJobAnalysis: () => throwError(() => ({ error: { detail: 'nope' } })) });
    expect(fixture.nativeElement.querySelector('.job-analysis-error')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run it to verify failure**

Run: `npm test -- --watch=false --include "**/job.component.spec.ts"`
Expected: FAIL — `JobDetailComponent` doesn't exist.

- [ ] **Step 3: Create the component**

Create `frontend/src/app/pages/job/job.component.ts`:
```typescript
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, Location } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NormalizedJob } from '../ingestion/models/normalized-job.model';
import { JobAnalysis } from '../ingestion/models/job-analysis.model';
import { IngestionService } from '../../core/services/ingestion.service';
import { ApplicationsService } from '../../core/services/applications.service';
import { DeepAnalysisComponent } from '../ingestion/components/deep-analysis/deep-analysis.component';
import { JobDescriptionComponent } from '../ingestion/components/job-description/job-description.component';
import { FeedbackControlsComponent } from '../ingestion/components/feedback-controls/feedback-controls.component';
import { formatScorePercent } from '../../core/utils/format-score-percent';
import { scoreColor } from '../../core/utils/score-color';

type Feature = 'matching' | 'optimization' | 'interview';

@Component({
  selector: 'app-job-detail',
  standalone: true,
  imports: [DatePipe, RouterLink, DeepAnalysisComponent, JobDescriptionComponent, FeedbackControlsComponent],
  templateUrl: './job.component.html',
  styleUrl: './job.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JobDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private location = inject(Location);
  private ingestion = inject(IngestionService);
  private applications = inject(ApplicationsService);
  private destroyRef = inject(DestroyRef);

  scoreColor = scoreColor;

  job = signal<NormalizedJob | null>(null);
  loading = signal(true);
  error = signal(false);

  analysis = signal<JobAnalysis | null>(null);
  analysisLoading = signal(false);
  analysisError = signal('');

  tracking = signal(false);

  pillScore = computed<number | null>(() => {
    const j = this.job();
    return j ? (j.llm_score ?? j.match_score) : null;
  });
  scorePercent = computed(() => formatScorePercent(this.pillScore()));
  tracked = computed(() => {
    const j = this.job();
    return j ? this.ingestion.trackedJobIds().has(j.id) : false;
  });

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    if (!id) {
      this.error.set(true);
      this.loading.set(false);
      return;
    }
    this.ingestion.getJob(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (j) => {
        this.job.set(j);
        this.loading.set(false);
        this.loadAnalysis(id);
      },
      error: () => {
        this.error.set(true);
        this.loading.set(false);
      },
    });
  }

  private loadAnalysis(id: string): void {
    const cached = this.ingestion.getCachedAnalysis(id);
    if (cached) {
      this.analysis.set(cached);
      return;
    }
    this.analysisLoading.set(true);
    this.analysisError.set('');
    this.ingestion.getJobAnalysis(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (a) => {
        this.analysis.set(a);
        this.analysisLoading.set(false);
      },
      error: (err) => {
        this.analysisError.set(err?.error?.detail || 'Deep analysis failed');
        this.analysisLoading.set(false);
      },
    });
  }

  retryAnalysis(): void {
    const j = this.job();
    if (j) this.loadAnalysis(j.id);
  }

  track(): void {
    const j = this.job();
    if (!j || this.tracked() || this.tracking()) return;
    this.tracking.set(true);
    this.applications.createFromJob(j.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.ingestion.markTracked(j.id);
        this.tracking.set(false);
      },
      error: () => {
        this.ingestion.markTracked(j.id);
        this.tracking.set(false);
      },
    });
  }

  goTo(feature: Feature): void {
    const j = this.job();
    if (j) this.router.navigate([`/dashboard/${feature}`], { queryParams: { job_id: j.id } });
  }

  back(): void {
    this.location.back();
  }
}
```

- [ ] **Step 4: Create the template**

Create `frontend/src/app/pages/job/job.component.html`:
```html
<div class="job-page">
  <button type="button" class="job-back" (click)="back()">← Back</button>

  @if (loading()) {
    <p class="job-state">Loading…</p>
  } @else if (error() || !job()) {
    <p class="job-state job-state-error">Couldn't load this job.</p>
  } @else if (job(); as j) {
    <header class="job-header">
      <h1 class="job-title">{{ j.title || 'Untitled role' }}</h1>
      <a class="job-company" [routerLink]="['/dashboard/company', j.company]">{{ j.company }}</a>
      <div class="job-facts">
        <span class="job-fact job-fact-source">{{ j.source }}</span>
        @if (j.location) { <span class="job-fact">📍 {{ j.location }}</span> }
        @if (j.salary_range) { <span class="job-fact">💰 {{ j.salary_range }}</span> }
        @if (j.posted_date) { <span class="job-fact">📅 {{ j.posted_date | date: 'mediumDate' }}</span> }
        @if (j.department) { <span class="job-fact">🏷 {{ j.department }}</span> }
      </div>
      @if (pillScore() !== null) {
        <div class="job-score">
          <span class="job-score-num" [style.color]="scoreColor(pillScore())">{{ scorePercent() }}</span>
          <span class="job-score-label">match score</span>
          @if (j.verdict) {
            <span class="job-verdict" [style.color]="scoreColor(pillScore())" [style.border-color]="scoreColor(pillScore())">{{ j.verdict }} fit</span>
          }
        </div>
      }
    </header>

    <div class="job-actions">
      <a [href]="j.url" target="_blank" rel="noopener" class="job-btn job-btn-primary">View Original ↗</a>
      @if (tracked()) {
        <button type="button" class="job-btn" disabled>Tracked ✓</button>
      } @else if (tracking()) {
        <button type="button" class="job-btn" disabled>Tracking…</button>
      } @else {
        <button type="button" class="job-btn" (click)="track()">Track</button>
      }
      <button type="button" class="job-btn" (click)="goTo('matching')">Match</button>
      <button type="button" class="job-btn" (click)="goTo('optimization')">Optimize CV</button>
      <button type="button" class="job-btn" (click)="goTo('interview')">Prep Interview</button>
    </div>

    <section class="job-feedback">
      <app-feedback-controls [jobId]="j.id" />
    </section>

    @if (j.reasons.length || j.dealbreakers.length) {
      <section class="job-card">
        <h2 class="job-section-label">Why this score</h2>
        @if (j.reasons.length) {
          <ul class="reason-list">
            @for (r of j.reasons; track r) { <li class="reason-item">{{ r }}</li> }
          </ul>
        }
        @if (j.dealbreakers.length) {
          <ul class="reason-list dealbreaker-list">
            @for (d of j.dealbreakers; track d) { <li class="dealbreaker-item">⚠ {{ d }}</li> }
          </ul>
        }
      </section>
    }

    <section class="job-card">
      <h2 class="job-section-label">Deep analysis</h2>
      @if (analysisLoading()) {
        <p class="job-analysis-state">Running advanced model…</p>
      } @else if (analysisError()) {
        <div class="job-analysis-state job-analysis-error">
          <p>{{ analysisError() }}</p>
          <button type="button" class="job-btn" (click)="retryAnalysis()">Retry</button>
        </div>
      } @else if (analysis(); as a) {
        <app-deep-analysis [analysis]="a" />
      } @else {
        <p class="job-analysis-state">No deep analysis available.</p>
      }
    </section>

    @if (j.skills.length) {
      <section class="job-card">
        <h2 class="job-section-label">Skills</h2>
        <div class="job-chips">
          @for (s of j.skills; track s) { <span class="job-tag">{{ s }}</span> }
        </div>
      </section>
    }

    <section class="job-card">
      <h2 class="job-section-label">Description</h2>
      <app-job-description [description]="j.description" />
    </section>

    @if (j.categories.length) {
      <section class="job-card">
        <h2 class="job-section-label">Categories</h2>
        <div class="job-chips">
          @for (c of j.categories; track c) { <span class="job-tag">{{ c }}</span> }
        </div>
      </section>
    }
  }
</div>
```

- [ ] **Step 5: Create the styles**

Create `frontend/src/app/pages/job/job.component.scss`:
```scss
.job-page { padding: 1.5rem 1.75rem 2.5rem; max-width: 860px; }

.job-back {
  background: none;
  border: none;
  padding: 0;
  margin-bottom: 1rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
  cursor: pointer;

  &:hover { color: var(--accent); }
}

.job-state { color: var(--text-muted); font-size: 0.9rem; }
.job-state-error { color: var(--danger); }

.job-header { margin-bottom: 1.25rem; }
.job-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.7rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
.job-company {
  display: inline-block;
  margin-top: 0.2rem;
  font-size: 1rem;
  font-weight: 600;
  color: var(--accent-text);
  text-decoration: none;

  &:hover { text-decoration: underline; }
}
.job-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.75rem;
}
.job-fact {
  background: var(--bg-inset);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-full);
  padding: 0.2rem 0.65rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
}
.job-fact-source { text-transform: capitalize; }
.job-score {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  margin-top: 0.9rem;
}
.job-score-num { font-family: var(--font-display); font-size: 1.6rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.job-score-label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.job-verdict {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: capitalize;
  border: 1px solid;
  border-radius: var(--radius-full);
  padding: 0.1rem 0.55rem;
}

.job-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
}
.job-btn {
  font: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  padding: 0.45rem 0.9rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-default);
  background: var(--bg-card);
  color: var(--text-primary);
  text-decoration: none;
  cursor: pointer;

  &:hover:not([disabled]) { border-color: var(--accent); color: var(--accent); }
  &[disabled] { opacity: 0.6; cursor: default; }
}
.job-btn-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;

  &:hover { background: var(--accent-hover); border-color: var(--accent-hover); color: #fff; }
}

.job-feedback { margin-bottom: 1.25rem; }

.job-card {
  margin-bottom: 1rem;
  padding: 1.1rem 1.25rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.job-section-label {
  display: block;
  margin: 0 0 0.6rem;
  font-family: var(--font-display);
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.reason-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.3rem; }
.reason-item, .dealbreaker-item { font-size: 0.875rem; color: var(--text-secondary); }
.dealbreaker-list { margin-top: 0.5rem; }
.dealbreaker-item { color: var(--danger); }

.job-analysis-state { color: var(--text-muted); font-size: 0.9rem; }
.job-analysis-error { color: var(--danger); }
.job-analysis-error .job-btn { margin-top: 0.5rem; color: var(--text-primary); }

.job-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.job-tag {
  background: var(--accent-subtle);
  color: var(--accent-text);
  border-radius: var(--radius-full);
  padding: 0.2rem 0.6rem;
  font-size: 0.8rem;
}
```

- [ ] **Step 6: Register the route**

In `app.routes.ts`, add inside the dashboard `children` array, directly after the `company/:name` route added in the previous feature:
```typescript
      { path: 'company/:name', loadComponent: () => import('./pages/company/company.component').then(m => m.CompanyComponent) },
      { path: 'job/:id', loadComponent: () => import('./pages/job/job.component').then(m => m.JobDetailComponent) },
```

- [ ] **Step 7: Run the spec + lint**

Run: `npm test -- --watch=false --include "**/job.component.spec.ts"` then `npx ng lint`
Expected: 3 specs PASS; lint clean.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/pages/job/ frontend/src/app/app.routes.ts
git commit -m "feat(ingestion): add dedicated job detail page with full analysis"
```

---

## Task 3: Company page links jobs to the detail page

**Files:**
- Modify: `frontend/src/app/pages/company/company.component.html`
- Test: `frontend/src/app/pages/company/company.component.spec.ts`

- [ ] **Step 1: Add the failing assertion**

In `company.component.spec.ts`, add this test inside the `describe` block (the existing `mount`/`job`/`page` helpers and `provideRouter([])` are already set up):
```typescript
  it('links each job to its detail page', () => {
    const service = { queryJobs: (tab: string) => of(page(tab === 'boards' ? [job()] : [])) };
    const fixture = mount(service);
    const link = fixture.nativeElement.querySelector('a.company-job-title') as HTMLAnchorElement;
    expect(link?.getAttribute('href')).toBe('/dashboard/job/1');
  });
```
(The `job()` helper in this spec already sets `id: '1'`.)

- [ ] **Step 2: Run it to verify failure**

Run: `npm test -- --watch=false --include "**/company.component.spec.ts"`
Expected: FAIL — the link still points at `/dashboard/ingestion?job_id=1`.

- [ ] **Step 3: Update the link**

In `company.component.html`, change the job title link from:
```html
            <a class="company-job-title" routerLink="/dashboard/ingestion" [queryParams]="{ job_id: job.id }">{{ job.title }}</a>
```
to:
```html
            <a class="company-job-title" [routerLink]="['/dashboard/job', job.id]">{{ job.title }}</a>
```

- [ ] **Step 4: Run the spec to verify it passes**

Run: `npm test -- --watch=false --include "**/company.component.spec.ts"`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Lint + commit**

```bash
cd frontend && npx ng lint && cd ..
git add frontend/src/app/pages/company/company.component.html frontend/src/app/pages/company/company.component.spec.ts
git commit -m "feat(analytics): link company-page jobs to the job detail page"
```

---

## Task 4: Full verification + live check

**No code.**

- [ ] **Step 1: Frontend — all affected specs**

Run (from `frontend/`): `npm test -- --watch=false --include "**/pages/job/**/*.spec.ts" --include "**/pages/company/**/*.spec.ts" --include "**/job-description.component.spec.ts" --include "**/job-detail-panel.component.spec.ts"`
Expected: all pass.

- [ ] **Step 2: Lint**

Run: `npx ng lint` (from `frontend/`). Expected: clean.

- [ ] **Step 3: Live check (servers already on :4200/:8000)**

  1. `/dashboard/ingestion` → open a job (View) → panel shows description + a "Full analysis — View pros, cons & breakdown →" link and NO inline deep-analysis toggle.
  2. Click that link → lands on `/dashboard/job/:id`; header shows title + company (linking to the company page) + score; the deep analysis auto-loads (pros/cons/dimensions); actions present.
  3. From `/dashboard/analytics` → a company → a job title → lands on `/dashboard/job/:id` directly (not the ingestion panel).
  4. No console errors.

- [ ] **Step 4: Final confirmation** — all specs green, lint clean, both flows verified live.

---

## Self-review notes

- **Spec coverage:** dedicated page with header/company-link/description/auto-analysis/actions (Task 2) ✓; slim panel — deep analysis removed, "View full analysis →" added (Task 1) ✓; shared `JobDescriptionComponent` used by panel + page (Tasks 1, 2) ✓; company-page jobs → detail page (Task 3) ✓; auto-load analysis cache-backed (Task 2 `loadAnalysis`) ✓; no backend changes ✓.
- **Type consistency:** `JobDescriptionComponent` input `description: string` (Task 1) ↔ used in panel and page (`[description]="…"`); `IngestionService.getJob`/`getJobAnalysis`/`getCachedAnalysis`/`trackedJobIds`/`markTracked` and `ApplicationsService.createFromJob` match their real signatures; route `job/:id` ↔ `paramMap.get('id')`.
- **Known cleanup in Task 1:** after removing the analysis code, verify `IngestionService`/`destroyRef` are unused in the panel and remove their imports/injections (lint will catch unused, but remove deliberately).
- **No placeholders** — Task 1 Step 9 now names the exact tests to delete, the mock plumbing to remove, and the `mount()`/`navigate` helpers the panel spec already defines.

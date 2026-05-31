# Preference Feedback — Frontend Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Angular UI so the user can give explicit feedback on jobs (thumbs up/down, not-interested, more-like-this) and see/reset the learned preference tuning, wiring the existing `/preference/*` backend endpoints into the app.

**Architecture:** A root-injectable `PreferenceService` (mirroring `tracking.service.ts`) wraps the four endpoints. A standalone `FeedbackControlsComponent` (OnPush, signals) renders the four actions, calls the service fire-and-forget with optimistic state, and emits `feedbackSubmitted` on success. It is embedded both in the job detail panel (full labels) and on each list-card row (compact icons). A `PreferenceTuningComponent` reads `/explain` and offers a guarded reset, mounted in the ingestion page toolbar. The ingestion page dims a job session-only on `not_interested` and debounce-refetches the list after any feedback so re-ranking is reflected.

**Tech Stack:** Angular 21 (standalone components, signals, OnPush), RxJS, vitest + `@angular/build:unit-test` + `@angular/common/http/testing`.

**Spec:** `docs/superpowers/specs/2026-05-31-preference-feedback-frontend-design.md`

**Confirmed decisions (from review):**
- Controls live on the **detail panel + compact list-card icons**.
- `not_interested` → **session-only dim** (cleared on any refetch; no backend persistence).
- After feedback → **debounced opt-in refetch** of the list (interval from `environment.feedbackRefetchDebounceMs`).

**Conventions observed (follow exactly):**
- Services: `@Injectable({ providedIn: 'root' })`, `constructor(private http: HttpClient) {}`, hit `` `${environment.apiUrl}/...` ``, return `Observable`s (see `frontend/src/app/core/services/tracking.service.ts`).
- Models: one interface/type per file under `pages/<area>/models/`, imported by direct file path (no barrel) — e.g. `frontend/src/app/pages/tracking/models/tracked-application.model.ts`.
- Components: standalone, `changeDetection: ChangeDetectionStrategy.OnPush`, `input`/`output`/`signal`/`computed`, separate `.html`/`.scss` files (see `job-detail-panel.component.ts`).
- Tests: vitest globals (`describe`/`it`/`expect`/`vi` — no imports needed), `TestBed`, `provideHttpClient()` + `provideHttpClientTesting()` for service tests.
- Run tests: `cd frontend && npm test`. Build check: `cd frontend && npm run build`.

---

## File Structure

**Create:**
- `frontend/src/app/pages/ingestion/models/feedback-kind.model.ts` — `FeedbackKind` string-union type.
- `frontend/src/app/pages/ingestion/models/feedback-signal.model.ts` — `FeedbackSignal` interface.
- `frontend/src/app/pages/ingestion/models/preference-explanation.model.ts` — `PreferenceExplanation` interface.
- `frontend/src/app/core/services/preference.service.ts` — `PreferenceService`.
- `frontend/src/app/core/services/preference.service.spec.ts` — service test.
- `frontend/src/app/pages/ingestion/components/feedback-controls/feedback-controls.component.ts` / `.html` / `.scss` — `FeedbackControlsComponent`.
- `frontend/src/app/pages/ingestion/components/feedback-controls/feedback-controls.component.spec.ts` — component test.
- `frontend/src/app/pages/ingestion/components/preference-tuning/preference-tuning.component.ts` / `.html` / `.scss` — `PreferenceTuningComponent`.
- `frontend/src/app/pages/ingestion/components/preference-tuning/preference-tuning.component.spec.ts` — component test.

**Modify:**
- `frontend/src/environments/environment.ts` and `environment.prod.ts` — add `feedbackRefetchDebounceMs`.
- `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.ts` / `.html` — embed feedback controls, forward `feedbackSubmitted`.
- `frontend/src/app/pages/ingestion/ingestion.component.ts` / `.html` — list-card compact controls, session dim, debounced refetch, tuning panel; forward detail-panel feedback.

---

## Task 1: Frontend models

**Files:**
- Create: `frontend/src/app/pages/ingestion/models/feedback-kind.model.ts`
- Create: `frontend/src/app/pages/ingestion/models/feedback-signal.model.ts`
- Create: `frontend/src/app/pages/ingestion/models/preference-explanation.model.ts`

No test of its own — these are type-only files exercised by Tasks 2–4.

- [ ] **Step 1: Create `feedback-kind.model.ts`**

```typescript
// Mirrors backend hiresense.preference.domain.FeedbackKind (explicit Phase 1 members).
export type FeedbackKind = 'thumbs_up' | 'thumbs_down' | 'not_interested' | 'more_like_this';
```

- [ ] **Step 2: Create `feedback-signal.model.ts`**

```typescript
import { FeedbackKind } from './feedback-kind.model';

// Mirrors backend FeedbackSignalResponse.
export interface FeedbackSignal {
  id: string | null;
  job_id: string;
  kind: FeedbackKind;
  created_at: string | null;
}
```

- [ ] **Step 3: Create `preference-explanation.model.ts`**

```typescript
// Mirrors backend PreferenceExplanation.
export interface PreferenceExplanation {
  active: boolean;
  total_signals: number;
  positive_count: number;
  negative_count: number;
  counts_by_kind: Record<string, number>;
  drift_magnitude: number;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/ingestion/models/feedback-kind.model.ts frontend/src/app/pages/ingestion/models/feedback-signal.model.ts frontend/src/app/pages/ingestion/models/preference-explanation.model.ts
git commit -m "feat(preference-fe): add feedback/explanation frontend models"
```

---

## Task 2: PreferenceService

**Files:**
- Create: `frontend/src/app/core/services/preference.service.ts`
- Test: `frontend/src/app/core/services/preference.service.spec.ts`

- [ ] **Step 1: Write the failing test**

```typescript
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { PreferenceService } from './preference.service';
import { environment } from '../../../environments/environment';

describe('PreferenceService', () => {
  let service: PreferenceService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [PreferenceService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PreferenceService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('submitFeedback POSTs job_id and kind', () => {
    service.submitFeedback('job-1', 'thumbs_up').subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/preference/feedback`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ job_id: 'job-1', kind: 'thumbs_up' });
    req.flush({ id: 's1', job_id: 'job-1', kind: 'thumbs_up', created_at: null });
  });

  it('explain GETs /preference/explain', () => {
    service.explain().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/preference/explain`);
    expect(req.request.method).toBe('GET');
    req.flush({
      active: false, total_signals: 0, positive_count: 0,
      negative_count: 0, counts_by_kind: {}, drift_magnitude: 0,
    });
  });

  it('signals GETs /preference/signals', () => {
    service.signals().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/preference/signals`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('reset POSTs to /preference/reset', () => {
    service.reset().subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/preference/reset`);
    expect(req.request.method).toBe('POST');
    req.flush(null);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — cannot resolve `./preference.service` (module not found).

- [ ] **Step 3: Write the implementation**

```typescript
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { FeedbackKind } from '../../pages/ingestion/models/feedback-kind.model';
import { FeedbackSignal } from '../../pages/ingestion/models/feedback-signal.model';
import { PreferenceExplanation } from '../../pages/ingestion/models/preference-explanation.model';

@Injectable({ providedIn: 'root' })
export class PreferenceService {
  constructor(private http: HttpClient) {}

  submitFeedback(jobId: string, kind: FeedbackKind): Observable<FeedbackSignal> {
    return this.http.post<FeedbackSignal>(`${environment.apiUrl}/preference/feedback`, {
      job_id: jobId,
      kind,
    });
  }

  explain(): Observable<PreferenceExplanation> {
    return this.http.get<PreferenceExplanation>(`${environment.apiUrl}/preference/explain`);
  }

  signals(): Observable<FeedbackSignal[]> {
    return this.http.get<FeedbackSignal[]>(`${environment.apiUrl}/preference/signals`);
  }

  reset(): Observable<void> {
    return this.http.post<void>(`${environment.apiUrl}/preference/reset`, {});
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS — all four `PreferenceService` specs green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/core/services/preference.service.ts frontend/src/app/core/services/preference.service.spec.ts
git commit -m "feat(preference-fe): add PreferenceService wrapping /preference endpoints"
```

---

## Task 3: FeedbackControlsComponent

**Files:**
- Create: `frontend/src/app/pages/ingestion/components/feedback-controls/feedback-controls.component.ts`
- Create: `frontend/src/app/pages/ingestion/components/feedback-controls/feedback-controls.component.html`
- Create: `frontend/src/app/pages/ingestion/components/feedback-controls/feedback-controls.component.scss`
- Test: `frontend/src/app/pages/ingestion/components/feedback-controls/feedback-controls.component.spec.ts`

- [ ] **Step 1: Write the failing test**

```typescript
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { FeedbackControlsComponent } from './feedback-controls.component';
import { PreferenceService } from '../../../../core/services/preference.service';

describe('FeedbackControlsComponent', () => {
  let submitFeedback: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    submitFeedback = vi.fn().mockReturnValue(
      of({ id: 's', job_id: 'j1', kind: 'thumbs_up', created_at: null }),
    );
    await TestBed.configureTestingModule({
      imports: [FeedbackControlsComponent],
      providers: [{ provide: PreferenceService, useValue: { submitFeedback } }],
    }).compileComponents();
  });

  function mount(jobId = 'j1') {
    const fixture = TestBed.createComponent(FeedbackControlsComponent);
    fixture.componentRef.setInput('jobId', jobId);
    fixture.detectChanges();
    return fixture;
  }

  it('renders four feedback buttons', () => {
    const fixture = mount();
    const buttons = fixture.nativeElement.querySelectorAll('button.fb-btn');
    expect(buttons.length).toBe(4);
  });

  it('calls submitFeedback with the clicked kind', () => {
    const fixture = mount();
    const buttons = fixture.nativeElement.querySelectorAll('button.fb-btn');
    (buttons[0] as HTMLButtonElement).click();
    expect(submitFeedback).toHaveBeenCalledWith('j1', 'thumbs_up');
  });

  it('emits feedbackSubmitted on success', () => {
    const fixture = mount();
    let emitted: string | null = null;
    fixture.componentInstance.feedbackSubmitted.subscribe((k) => (emitted = k));
    (fixture.nativeElement.querySelector('button.fb-btn') as HTMLButtonElement).click();
    expect(emitted).toBe('thumbs_up');
    expect(fixture.componentInstance.lastSent()).toBe('thumbs_up');
  });

  it('shows error affordance and does not emit on failure', () => {
    submitFeedback.mockReturnValue(throwError(() => new Error('fail')));
    const fixture = mount();
    let emitted = false;
    fixture.componentInstance.feedbackSubmitted.subscribe(() => (emitted = true));
    (fixture.nativeElement.querySelector('button.fb-btn') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.componentInstance.failed()).toBe(true);
    expect(emitted).toBe(false);
    expect(fixture.nativeElement.querySelector('.fb-error')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — cannot resolve `./feedback-controls.component`.

- [ ] **Step 3: Create the component class**

`feedback-controls.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { PreferenceService } from '../../../../core/services/preference.service';
import { FeedbackKind } from '../../models/feedback-kind.model';

interface FeedbackControl {
  kind: FeedbackKind;
  icon: string;
  label: string;
}

@Component({
  selector: 'app-feedback-controls',
  standalone: true,
  templateUrl: './feedback-controls.component.html',
  styleUrl: './feedback-controls.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FeedbackControlsComponent {
  private preferenceService = inject(PreferenceService);

  jobId = input.required<string>();
  /** Compact = icon-only, for list rows. Default shows labels (detail panel). */
  compact = input<boolean>(false);

  feedbackSubmitted = output<FeedbackKind>();

  pending = signal<FeedbackKind | null>(null);
  lastSent = signal<FeedbackKind | null>(null);
  failed = signal(false);

  readonly controls: FeedbackControl[] = [
    { kind: 'thumbs_up', icon: '👍', label: 'More relevant' },
    { kind: 'thumbs_down', icon: '👎', label: 'Less relevant' },
    { kind: 'not_interested', icon: '🚫', label: 'Not interested' },
    { kind: 'more_like_this', icon: '✨', label: 'More like this' },
  ];

  submit(kind: FeedbackKind): void {
    if (this.pending() !== null) return;
    this.pending.set(kind);
    this.failed.set(false);
    this.preferenceService.submitFeedback(this.jobId(), kind).subscribe({
      next: () => {
        this.pending.set(null);
        this.lastSent.set(kind);
        this.feedbackSubmitted.emit(kind);
      },
      error: () => {
        this.pending.set(null);
        this.failed.set(true);
      },
    });
  }
}
```

- [ ] **Step 4: Create the template**

`feedback-controls.component.html`:

```html
<div class="feedback-controls" [class.compact]="compact()">
  @for (c of controls; track c.kind) {
    <button
      type="button"
      class="fb-btn"
      [class.active]="lastSent() === c.kind"
      [disabled]="pending() !== null"
      [attr.aria-label]="c.label"
      [title]="c.label"
      (click)="submit(c.kind); $event.stopPropagation()"
    >
      <span class="fb-icon">{{ c.icon }}</span>
      @if (!compact()) {
        <span class="fb-label">{{ c.label }}</span>
      }
    </button>
  }
  @if (failed()) {
    <span class="fb-error" role="alert">Couldn't save — tap again</span>
  }
</div>
```

- [ ] **Step 5: Create the styles**

`feedback-controls.component.scss`:

```scss
.feedback-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.fb-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--border, #d0d0d0);
  border-radius: 6px;
  background: var(--surface, #fff);
  cursor: pointer;
  font-size: 0.85rem;
  line-height: 1;
  transition: background 0.15s, border-color 0.15s;

  &:hover:not(:disabled) {
    background: var(--surface-hover, #f3f4f6);
  }
  &:disabled {
    opacity: 0.6;
    cursor: default;
  }
  &.active {
    border-color: var(--accent, #4f46e5);
    background: var(--accent-soft, #eef2ff);
  }
}

.fb-icon {
  font-size: 1rem;
}

.compact {
  gap: 0.25rem;

  .fb-btn {
    padding: 0.2rem 0.35rem;
    font-size: 0.95rem;
  }
}

.fb-error {
  font-size: 0.75rem;
  color: var(--danger, #dc2626);
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS — all four `FeedbackControlsComponent` specs green.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/pages/ingestion/components/feedback-controls/
git commit -m "feat(preference-fe): add FeedbackControlsComponent"
```

---

## Task 4: PreferenceTuningComponent

**Files:**
- Create: `frontend/src/app/pages/ingestion/components/preference-tuning/preference-tuning.component.ts`
- Create: `frontend/src/app/pages/ingestion/components/preference-tuning/preference-tuning.component.html`
- Create: `frontend/src/app/pages/ingestion/components/preference-tuning/preference-tuning.component.scss`
- Test: `frontend/src/app/pages/ingestion/components/preference-tuning/preference-tuning.component.spec.ts`

- [ ] **Step 1: Write the failing test**

```typescript
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { PreferenceTuningComponent } from './preference-tuning.component';
import { PreferenceService } from '../../../../core/services/preference.service';

const ACTIVE_EXPLAIN = {
  active: true,
  total_signals: 3,
  positive_count: 2,
  negative_count: 1,
  counts_by_kind: { thumbs_up: 2, thumbs_down: 1 },
  drift_magnitude: 0.42,
};

describe('PreferenceTuningComponent', () => {
  let explain: ReturnType<typeof vi.fn>;
  let reset: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    explain = vi.fn().mockReturnValue(of(ACTIVE_EXPLAIN));
    reset = vi.fn().mockReturnValue(of(undefined));
    await TestBed.configureTestingModule({
      imports: [PreferenceTuningComponent],
      providers: [{ provide: PreferenceService, useValue: { explain, reset } }],
    }).compileComponents();
  });

  function mount() {
    const fixture = TestBed.createComponent(PreferenceTuningComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('loads the explanation when expanded', () => {
    const fixture = mount();
    fixture.componentInstance.toggle();
    fixture.detectChanges();
    expect(explain).toHaveBeenCalled();
    expect(fixture.componentInstance.explanation()?.total_signals).toBe(3);
  });

  it('reset calls the service when confirmed', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fixture = mount();
    fixture.componentInstance.reset();
    expect(reset).toHaveBeenCalled();
  });

  it('reset does nothing when cancelled', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const fixture = mount();
    fixture.componentInstance.reset();
    expect(reset).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — cannot resolve `./preference-tuning.component`.

- [ ] **Step 3: Create the component class**

`preference-tuning.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { PreferenceService } from '../../../../core/services/preference.service';
import { PreferenceExplanation } from '../../models/preference-explanation.model';

@Component({
  selector: 'app-preference-tuning',
  standalone: true,
  templateUrl: './preference-tuning.component.html',
  styleUrl: './preference-tuning.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PreferenceTuningComponent {
  private preferenceService = inject(PreferenceService);

  explanation = signal<PreferenceExplanation | null>(null);
  expanded = signal(false);
  resetting = signal(false);

  toggle(): void {
    const next = !this.expanded();
    this.expanded.set(next);
    if (next) this.load();
  }

  load(): void {
    this.preferenceService.explain().subscribe({
      next: (e) => this.explanation.set(e),
      error: () => this.explanation.set(null),
    });
  }

  reset(): void {
    if (!confirm('Reset learned preferences? This clears all feedback-based tuning.')) return;
    this.resetting.set(true);
    this.preferenceService.reset().subscribe({
      next: () => {
        this.resetting.set(false);
        this.load();
      },
      error: () => this.resetting.set(false),
    });
  }
}
```

- [ ] **Step 4: Create the template**

`preference-tuning.component.html`:

```html
<div class="preference-tuning">
  <button type="button" class="tuning-toggle" (click)="toggle()">
    🎚 Tuning
  </button>

  @if (expanded()) {
    <div class="tuning-panel">
      @if (explanation(); as e) {
        @if (e.active) {
          <p class="tuning-status">
            Personalizing from <strong>{{ e.total_signals }}</strong> signal(s)
            ({{ e.positive_count }} positive, {{ e.negative_count }} negative).
          </p>
          <p class="tuning-drift">Drift magnitude: {{ e.drift_magnitude.toFixed(2) }}</p>
          <ul class="tuning-counts">
            @for (entry of e.counts_by_kind | keyvalue; track entry.key) {
              <li>{{ entry.key }}: {{ entry.value }}</li>
            }
          </ul>
          <button
            type="button"
            class="btn-reset"
            [disabled]="resetting()"
            (click)="reset()"
          >
            @if (resetting()) { Resetting… } @else { Reset tuning }
          </button>
        } @else {
          <p class="tuning-empty">No tuning yet — give feedback to personalize ranking.</p>
        }
      } @else {
        <p class="tuning-empty">No tuning data available.</p>
      }
    </div>
  }
</div>
```

NOTE: the `keyvalue` pipe requires `KeyValuePipe` from `@angular/common` in the component `imports`. Update the `@Component` decorator from Step 3 to:

```typescript
import { KeyValuePipe } from '@angular/common';
// ...
@Component({
  selector: 'app-preference-tuning',
  standalone: true,
  imports: [KeyValuePipe],
  templateUrl: './preference-tuning.component.html',
  styleUrl: './preference-tuning.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
```

- [ ] **Step 5: Create the styles**

`preference-tuning.component.scss`:

```scss
.preference-tuning {
  position: relative;
  display: inline-block;
}

.tuning-toggle {
  padding: 0.45rem 0.75rem;
  border: 1px solid var(--border, #d0d0d0);
  border-radius: 6px;
  background: var(--surface, #fff);
  cursor: pointer;
  font-size: 0.85rem;
}

.tuning-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 0.4rem);
  z-index: 20;
  width: 18rem;
  padding: 0.85rem;
  border: 1px solid var(--border, #d0d0d0);
  border-radius: 8px;
  background: var(--surface, #fff);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  font-size: 0.85rem;
}

.tuning-status,
.tuning-drift,
.tuning-empty {
  margin: 0 0 0.5rem;
}

.tuning-counts {
  margin: 0 0 0.75rem;
  padding-left: 1.1rem;
}

.btn-reset {
  padding: 0.35rem 0.7rem;
  border: 1px solid var(--danger, #dc2626);
  border-radius: 6px;
  background: transparent;
  color: var(--danger, #dc2626);
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: default;
  }
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS — all three `PreferenceTuningComponent` specs green.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/pages/ingestion/components/preference-tuning/
git commit -m "feat(preference-fe): add PreferenceTuningComponent"
```

---

## Task 5: Add the refetch-debounce config value

**Files:**
- Modify: `frontend/src/environments/environment.ts`
- Modify: `frontend/src/environments/environment.prod.ts`

Per the no-hardcoded-values rule, the post-feedback refetch debounce is a config value, not a literal in the component.

- [ ] **Step 1: Add to `environment.ts`**

Change the object to:

```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000',
  // Debounce (ms) before the job list refetches after preference feedback,
  // so rapid clicks coalesce into a single re-rank fetch.
  feedbackRefetchDebounceMs: 2500,
};
```

- [ ] **Step 2: Add to `environment.prod.ts`**

```typescript
export const environment = {
  production: true,
  apiUrl: '/api',
  feedbackRefetchDebounceMs: 2500,
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/environments/environment.ts frontend/src/environments/environment.prod.ts
git commit -m "feat(preference-fe): add feedbackRefetchDebounceMs config"
```

---

## Task 6: Embed feedback controls in the job detail panel

**Files:**
- Modify: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.ts`
- Modify: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.html`

- [ ] **Step 1: Update the component class**

In `job-detail-panel.component.ts`:

1. Add imports near the top (after the existing `DeepAnalysisComponent` import):

```typescript
import { FeedbackControlsComponent } from '../feedback-controls/feedback-controls.component';
import { FeedbackKind } from '../../models/feedback-kind.model';
```

2. Add `FeedbackControlsComponent` to the `imports` array of the `@Component` decorator:

```typescript
  imports: [DatePipe, DeepAnalysisComponent, FeedbackControlsComponent],
```

3. Add a forwarding output next to the existing `track = output<string>();` (after line 30):

```typescript
  feedbackSubmitted = output<FeedbackKind>();
```

- [ ] **Step 2: Embed the controls in the template**

In `job-detail-panel.component.html`, immediately after the match-header `</div>` that closes the match-score section (after line 48, before the "Why this score" block), insert:

```html
      <!-- Preference feedback -->
      <div class="panel-section feedback-section">
        <app-feedback-controls
          [jobId]="job().id"
          (feedbackSubmitted)="feedbackSubmitted.emit($event)"
        />
      </div>
```

- [ ] **Step 3: Verify build + existing tests still pass**

Run: `cd frontend && npm run build`
Expected: build succeeds (no template/type errors).

Run: `cd frontend && npm test`
Expected: PASS — all suites green (no regression in existing specs).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.ts frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.html
git commit -m "feat(preference-fe): embed feedback controls in job detail panel"
```

---

## Task 7: Wire the ingestion page — list icons, session dim, debounced refetch, tuning panel

**Files:**
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.ts`
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.html`

- [ ] **Step 1: Update the component class — imports, debounce, dim state, handlers**

In `ingestion.component.ts`:

1. Extend the `@angular/core` import to add `DestroyRef`:

```typescript
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
```

2. Add these imports after the existing `DatePipe` import:

```typescript
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { FeedbackControlsComponent } from './components/feedback-controls/feedback-controls.component';
import { PreferenceTuningComponent } from './components/preference-tuning/preference-tuning.component';
import { FeedbackKind } from './models/feedback-kind.model';
```

3. Add the two new components to the `@Component` `imports` array:

```typescript
  imports: [
    PaginationComponent,
    JobFiltersComponent,
    JobDetailPanelComponent,
    DatePipe,
    FeedbackControlsComponent,
    PreferenceTuningComponent,
  ],
```

4. Add a `DestroyRef` injection alongside the existing `inject(...)` fields (after `private route = inject(ActivatedRoute);`):

```typescript
  private destroyRef = inject(DestroyRef);
```

5. Add the dim state signal and the refetch subject as fields (after the `selectedJob` signal, around line 77):

```typescript
  // Jobs the user marked "not interested" this session — dimmed locally until
  // the next refetch (no backend "hidden" persistence; see plan/spec).
  dimmedJobIds = signal<Set<string>>(new Set<string>());

  // Coalesces rapid feedback into one re-rank refetch.
  private feedbackRefetch$ = new Subject<void>();
```

6. In `ngOnInit`, wire the debounced refetch. Replace the existing `ngOnInit` body's start so it reads:

```typescript
  ngOnInit(): void {
    this.feedbackRefetch$
      .pipe(debounceTime(environment.feedbackRefetchDebounceMs), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.loadJobs());
    this.loadPortals();
    this.loadJobs();
    this.openDetailFromQueryParam();
  }
```

7. In `loadJobs`, clear the session dim on every (re)fetch. Inside the `next:` handler of the `queryJobs(...).subscribe({...})` block, add `this.dimmedJobIds.set(new Set<string>());` as the first line:

```typescript
        next: (res) => {
          this.dimmedJobIds.set(new Set<string>());
          this.jobs.set(res.jobs);
          this.total.set(res.total);
          this.totalPages.set(res.total_pages);
          this.loading.set(false);
        },
```

8. Add the feedback handler and a dim helper as new methods (e.g. after `onSortChange`):

```typescript
  onFeedback(jobId: string, kind: FeedbackKind): void {
    if (kind === 'not_interested') {
      const next = new Set(this.dimmedJobIds());
      next.add(jobId);
      this.dimmedJobIds.set(next);
    }
    this.feedbackRefetch$.next();
  }

  isDimmed(jobId: string): boolean {
    return this.dimmedJobIds().has(jobId);
  }
```

- [ ] **Step 2: Update the list-row template — compact controls + dim class**

In `ingestion.component.html`:

1. Add the `dimmed` class binding to the job row (line 169). Change:

```html
            <tr (click)="openDetail(job)" class="clickable-row" [class.closed]="job.status === 'closed'">
```

to:

```html
            <tr (click)="openDetail(job)" class="clickable-row" [class.closed]="job.status === 'closed'" [class.dimmed]="isDimmed(job.id)">
```

2. Add compact feedback controls in the actions cell. Inside `<td class="actions-cell">` (after the `View` link on line 194, before the `@if (isTracked(job.id))` block), insert:

```html
                <app-feedback-controls
                  [jobId]="job.id"
                  [compact]="true"
                  (feedbackSubmitted)="onFeedback(job.id, $event)"
                  (click)="$event.stopPropagation()"
                />
```

- [ ] **Step 3: Wire the detail panel's feedback output**

In `ingestion.component.html`, add the `feedbackSubmitted` binding to the `<app-job-detail-panel>` element (after line 240 `(track)="trackJob($event)"`):

```html
  <app-job-detail-panel
    [job]="selectedJob()!"
    [tracked]="isTracked(selectedJob()!.id)"
    [tracking]="isTracking(selectedJob()!.id)"
    (close)="closeDetail()"
    (track)="trackJob($event)"
    (feedbackSubmitted)="onFeedback(selectedJob()!.id, $event)"
  />
```

- [ ] **Step 4: Mount the tuning panel in the toolbar**

In `ingestion.component.html`, inside `<div class="tab-actions">` (line 20), add the tuning panel before the existing fetch/scan `@if` block:

```html
    <div class="tab-actions">
      <app-preference-tuning />
      @if (activeTab() === 'boards') {
```

- [ ] **Step 5: Add the dim style**

In `frontend/src/app/pages/ingestion/ingestion.component.scss`, append:

```scss
.clickable-row.dimmed {
  opacity: 0.45;
  transition: opacity 0.2s;
}
```

- [ ] **Step 6: Verify build + tests**

Run: `cd frontend && npm run build`
Expected: build succeeds.

Run: `cd frontend && npm test`
Expected: PASS — all suites green.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/pages/ingestion/ingestion.component.ts frontend/src/app/pages/ingestion/ingestion.component.html frontend/src/app/pages/ingestion/ingestion.component.scss
git commit -m "feat(preference-fe): wire list-card feedback, session dim, debounced refetch, tuning panel"
```

---

## Task 8: Final verification

- [ ] **Step 1: Full test run**

Run: `cd frontend && npm test`
Expected: PASS — `PreferenceService` (4), `FeedbackControlsComponent` (4), `PreferenceTuningComponent` (3), plus pre-existing specs, all green.

- [ ] **Step 2: Production build**

Run: `cd frontend && npm run build`
Expected: build succeeds with no type/template errors.

- [ ] **Step 3: Manual smoke (optional, requires backend running)**

With the backend up (`cd backend && uv run python -m uvicorn ...` per project conventions) and `npm start`:
- Open the jobs list, click a thumbs icon on a row → no error, icon reflects last action.
- Click 🚫 on a row → row dims; after ~2.5s the list refetches and the dim clears.
- Open a job detail panel → full-label controls present and functional.
- Open the Tuning panel → shows counts after feedback; Reset prompts a confirm and clears tuning.

---

## Self-Review notes

- **Spec coverage:** capture explicit feedback (Tasks 3, 6, 7) ✓; make the loop visible + reset (Task 4, 7) ✓; Angular conventions — standalone/OnPush/signals/root service/`environment.apiUrl` (all tasks) ✓; `PreferenceService` with the four methods (Task 2) ✓; models mirroring backend (Task 1) ✓; controls on detail panel + list cards (Tasks 6, 7 — confirmed decision) ✓; session-only dim (Task 7) ✓; debounced refetch (Tasks 5, 7) ✓; error affordance via non-blocking inline message — no toast system exists, so the component shows an inline `.fb-error` (Task 3) ✓; auth via existing interceptor — no special handling needed ✓.
- **Type consistency:** `FeedbackKind` union reused across model, service, both components, and both parents; `feedbackSubmitted: output<FeedbackKind>` matches `onFeedback(jobId, kind: FeedbackKind)`; `submitFeedback(jobId, kind)` signature consistent between service and callers.
- **No placeholders:** every code step contains complete code.

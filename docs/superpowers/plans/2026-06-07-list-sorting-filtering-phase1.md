# List Sorting & Filtering — Phase 1 (Foundation + Ingestion) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ingestion page's 3-option sort dropdown with clickable, bidirectional column-header sorting, backed by a generalized backend sort resolver and a reusable frontend sortable-header pattern.

**Architecture:** Backend — a pure domain function `sort_jobs(jobs, sort)` parses a `<field>_<dir>` token, sorts nulls-last/case-insensitive, and is called from `filter_and_paginate`; the API whitelists the token and re-sorts the page after scoring only for match-field sorts. Frontend — a `createSortState` signal helper + a `SortableHeaderComponent` render clickable `<th>`s with ▲/▼ and `aria-sort`; the ingestion component emits `<field>_<dir>` tokens to the existing query param. A pure `sortItems` util is added for the client-side bare-list pages of later phases.

**Tech Stack:** Python 3.13 / Pydantic (backend domain, no framework deps), pytest. Angular 21 standalone + signals, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-07-sorting-filtering-design.md` (Phase 1 section).

**Sort token contract (shared FE/BE):** `<field>_<dir>` where `field ∈ {match, posted, title, company, location, source}`, `dir ∈ {asc, desc}`. `date_desc`/`date_asc` are accepted aliases for `posted_*`. Unknown/empty tokens preserve insertion order in the domain; the API substitutes `match_desc` for any non-whitelisted value.

---

## Backend

### Task 1: `sort_jobs` domain function

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/job_sort.py`
- Modify: `backend/src/hiresense/ingestion/domain/__init__.py` (re-export)
- Test: `backend/tests/unit/ingestion/test_job_sort.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/ingestion/test_job_sort.py
from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain import sort_jobs
from hiresense.ingestion.domain.models import NormalizedJob


def _job(id: str, *, score=None, date=None, title="", company="", location="", source="x"):
    return NormalizedJob(
        id=id, title=title, company=company, description="x", skills=[],
        location=location, source=source, source_type="api", url="x",
        match_score=score, posted_date=date,
    )


def test_none_token_preserves_order():
    jobs = [_job("a", score=0.3), _job("b", score=0.9)]
    assert [j.id for j in sort_jobs(jobs, None)] == ["a", "b"]


def test_unknown_token_preserves_order():
    jobs = [_job("a"), _job("b")]
    assert [j.id for j in sort_jobs(jobs, "bogus_desc")] == ["a", "b"]


def test_match_desc_and_asc():
    jobs = [_job("a", score=0.3), _job("b", score=0.9), _job("c", score=0.6)]
    assert [j.id for j in sort_jobs(jobs, "match_desc")] == ["b", "c", "a"]
    assert [j.id for j in sort_jobs(jobs, "match_asc")] == ["a", "c", "b"]


def test_match_nulls_last_regardless_of_direction():
    jobs = [_job("n1", score=None), _job("hi", score=0.9), _job("lo", score=0.1)]
    assert [j.id for j in sort_jobs(jobs, "match_desc")][-1] == "n1"
    assert [j.id for j in sort_jobs(jobs, "match_asc")][-1] == "n1"


def test_posted_desc_and_date_alias():
    jobs = [
        _job("old", date=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _job("new", date=datetime(2026, 5, 1, tzinfo=timezone.utc)),
    ]
    assert [j.id for j in sort_jobs(jobs, "posted_desc")] == ["new", "old"]
    assert [j.id for j in sort_jobs(jobs, "date_desc")] == ["new", "old"]
    assert [j.id for j in sort_jobs(jobs, "date_asc")] == ["old", "new"]


def test_posted_nulls_last():
    jobs = [_job("nd"), _job("d", date=datetime(2026, 5, 1, tzinfo=timezone.utc))]
    assert [j.id for j in sort_jobs(jobs, "posted_asc")] == ["d", "nd"]


def test_text_fields_case_insensitive_and_empty_last():
    jobs = [_job("z", title="zeta"), _job("a", title="Alpha"), _job("e", title="")]
    assert [j.id for j in sort_jobs(jobs, "title_asc")] == ["a", "z", "e"]


def test_company_and_source_sort():
    jobs = [_job("b", company="Beta", source="remotive"), _job("a", company="acme", source="jobicy")]
    assert [j.id for j in sort_jobs(jobs, "company_asc")] == ["a", "b"]
    assert [j.id for j in sort_jobs(jobs, "source_desc")] == ["a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_job_sort.py -v`
Expected: FAIL — `ImportError: cannot import name 'sort_jobs'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/hiresense/ingestion/domain/job_sort.py
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hiresense.ingestion.domain.models import NormalizedJob

# field token -> NormalizedJob attribute
_ATTR: dict[str, str] = {
    "match": "match_score",
    "posted": "posted_date",
    "title": "title",
    "company": "company",
    "location": "location",
    "source": "source",
}
_TEXT_FIELDS = {"title", "company", "location", "source"}
# Backward-compatible field aliases (the old dropdown emitted "date_*").
_ALIASES = {"date": "posted"}


def _parse(sort: str | None) -> tuple[str, bool] | None:
    """Return (field, reverse) for a valid token, else None.

    Token shape is ``<field>_<dir>`` with dir in {asc, desc}. Unknown fields
    or malformed tokens return None so callers preserve insertion order.
    """
    if not sort:
        return None
    field, _, direction = sort.rpartition("_")
    if direction not in ("asc", "desc") or not field:
        return None
    field = _ALIASES.get(field, field)
    if field not in _ATTR:
        return None
    return field, direction == "desc"


def _accessor(field: str) -> Callable[[NormalizedJob], Any]:
    attr = _ATTR[field]
    if field in _TEXT_FIELDS:
        return lambda j: (getattr(j, attr) or "").lower()
    return lambda j: getattr(j, attr)


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def sort_jobs(jobs: list[NormalizedJob], sort: str | None) -> list[NormalizedJob]:
    """Sort jobs by a ``<field>_<dir>`` token, nulls/empties always last.

    Returns a new list. An unrecognized or empty token preserves the input
    order (the API layer is responsible for substituting a default).
    """
    parsed = _parse(sort)
    if parsed is None:
        return list(jobs)
    field, reverse = parsed
    get = _accessor(field)
    present = [j for j in jobs if not _is_missing(get(j))]
    missing = [j for j in jobs if _is_missing(get(j))]
    present.sort(key=get, reverse=reverse)
    return present + missing
```

- [ ] **Step 4: Add the package re-export**

In `backend/src/hiresense/ingestion/domain/__init__.py`, add `sort_jobs` to the imports and `__all__` (follow the file's existing re-export style):

```python
from hiresense.ingestion.domain.job_sort import sort_jobs
```
and add `"sort_jobs"` to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_job_sort.py -v`
Expected: PASS (all 8 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/job_sort.py backend/src/hiresense/ingestion/domain/__init__.py backend/tests/unit/ingestion/test_job_sort.py
git commit -m "feat(ingestion): add generalized sort_jobs domain resolver"
```

---

### Task 2: Use `sort_jobs` in `filter_and_paginate`

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/job_filter.py:154-165` (the sort block) and its imports
- Test: `backend/tests/unit/ingestion/test_sort_options.py` (extend existing)

- [ ] **Step 1: Add new failing tests to the existing file**

Append to `backend/tests/unit/ingestion/test_sort_options.py`:

```python
def test_sort_title_asc_via_filter():
    jobs = [_job("z"), _job("a")]
    jobs[0].title = "zeta"
    jobs[1].title = "alpha"
    result = filter_and_paginate(jobs, JobQueryParams(sort="title_asc"))
    assert [j.id for j in result.jobs] == ["a", "z"]


def test_sort_match_asc_via_filter():
    jobs = [_job("a", 0.9), _job("b", 0.1)]
    result = filter_and_paginate(jobs, JobQueryParams(sort="match_asc"))
    assert [j.id for j in result.jobs] == ["b", "a"]
```

(The `_job` helper in this file takes positional `id, score, date`; set `.title` after construction as shown.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_sort_options.py -v`
Expected: the two new tests FAIL (title_asc/match_asc not handled), existing 5 still PASS.

- [ ] **Step 3: Replace the sort block in `job_filter.py`**

Delete lines 154-165 (the `if params.sort == "match_desc": ... elif ... "date_desc": ...` block) and replace with:

```python
    filtered = sort_jobs(filtered, params.sort)
```

Add the import near the other domain imports at the top of the file:

```python
from hiresense.ingestion.domain.job_sort import sort_jobs
```

The now-unused `_DATETIME_MIN_UTC` constant (line 15) is no longer referenced by the sort block — leave it only if another reference exists; otherwise delete line 15. Verify with:

Run: `cd backend && grep -n "_DATETIME_MIN_UTC" src/hiresense/ingestion/domain/job_filter.py`
Expected: no matches after deletion → remove the constant definition.

- [ ] **Step 4: Run the full ingestion sort/filter tests**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_sort_options.py tests/unit/ingestion/test_job_filter.py -v`
Expected: PASS (all, including the 2 new and the original 5).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/job_filter.py backend/tests/unit/ingestion/test_sort_options.py
git commit -m "refactor(ingestion): route filter_and_paginate sorting through sort_jobs"
```

---

### Task 3: API whitelist + generalized post-scoring re-sort

**Files:**
- Modify: `backend/src/hiresense/ingestion/api/routes.py` (line 173 default, lines 264-269 and 282-287 re-sorts)
- Test: `backend/tests/unit/ingestion/test_routes.py` (add cases)

- [ ] **Step 1: Add failing tests**

Append to `backend/tests/unit/ingestion/test_routes.py` (match the file's existing fixture/client setup — reuse the in-process client helper already used there):

```python
def test_jobs_accepts_title_asc_sort(client):
    resp = client.get("/ingestion/jobs", params={"tab": "boards", "sort": "title_asc"})
    assert resp.status_code == 200


def test_jobs_invalid_sort_falls_back_to_default(client):
    # An unknown token must not 422; it falls back to match_desc and returns 200.
    resp = client.get("/ingestion/jobs", params={"tab": "boards", "sort": "bogus_xyz"})
    assert resp.status_code == 200
```

(If `test_routes.py` builds the client differently, adapt the fixture name; the assertions stay the same.)

- [ ] **Step 2: Run to verify behavior**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_routes.py -k "sort" -v`
Expected: `title_asc` test may already pass (domain handles it); `invalid_sort` test passes too if no validation exists — confirm current behavior, then proceed to make the fallback explicit and intentional.

- [ ] **Step 3: Add the whitelist + fallback in `routes.py`**

Just above `effective_sort = sort or "match_desc"` (line 173), add a module-level constant near the top of the file (after imports):

```python
_ALLOWED_SORTS = frozenset(
    f"{field}_{direction}"
    for field in ("match", "posted", "title", "company", "location", "source")
    for direction in ("asc", "desc")
) | {"date_desc", "date_asc"}
```

Replace line 173:

```python
    effective_sort = sort or "match_desc"
```
with:
```python
    effective_sort = sort or "match_desc"
    if effective_sort not in _ALLOWED_SORTS:
        effective_sort = "match_desc"
```

- [ ] **Step 4: Generalize the two post-scoring re-sorts**

Add the import near the other domain imports:
```python
from hiresense.ingestion.domain import sort_jobs
```

Replace the semantic-pass re-sort (lines 264-269):
```python
        if effective_sort == "match_desc":
            result.jobs = sorted(
                result.jobs,
                key=lambda j: (j.match_score if j.match_score is not None else -1.0),
                reverse=True,
            )
```
with:
```python
        if effective_sort.startswith("match_"):
            result.jobs = sort_jobs(result.jobs, effective_sort)
```

Replace the quick-scoring re-sort (lines 282-287) identically:
```python
            if effective_sort.startswith("match_"):
                result.jobs = sort_jobs(result.jobs, effective_sort)
```

Rationale: only match-field sorts depend on scores computed after pagination; for every other field the order from `filter_and_paginate` is already final and stable.

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion/test_routes.py -v && uv run ruff check src/hiresense/ingestion`
Expected: PASS, no lint errors.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ingestion/api/routes.py backend/tests/unit/ingestion/test_routes.py
git commit -m "feat(ingestion): whitelist sort param and re-sort match fields post-scoring"
```

---

## Frontend

### Task 4: `createSortState` signal helper

**Files:**
- Create: `frontend/src/app/core/utils/sort-state.ts`
- Test: `frontend/src/app/core/utils/sort-state.spec.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/app/core/utils/sort-state.spec.ts
import { describe, expect, it } from 'vitest';
import { createSortState } from './sort-state';

type F = 'match' | 'posted' | 'title';

describe('createSortState', () => {
  it('exposes the initial field, direction and token', () => {
    const s = createSortState<F>('match', 'desc', ['title']);
    expect(s.field()).toBe('match');
    expect(s.dir()).toBe('desc');
    expect(s.token()).toBe('match_desc');
  });

  it('flips direction when toggling the active field', () => {
    const s = createSortState<F>('match', 'desc', ['title']);
    s.toggle('match');
    expect(s.dir()).toBe('asc');
    expect(s.token()).toBe('match_asc');
    s.toggle('match');
    expect(s.dir()).toBe('desc');
  });

  it('selects a new field with its default direction', () => {
    const s = createSortState<F>('match', 'desc', ['title']);
    s.toggle('title'); // text field -> asc default
    expect(s.field()).toBe('title');
    expect(s.dir()).toBe('asc');
    s.toggle('posted'); // non-text -> desc default
    expect(s.field()).toBe('posted');
    expect(s.dir()).toBe('desc');
  });

  it('reports the active field', () => {
    const s = createSortState<F>('match', 'desc', ['title']);
    expect(s.isActive('match')).toBe(true);
    expect(s.isActive('title')).toBe(false);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm test -- --include "**/sort-state.spec.ts"`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/src/app/core/utils/sort-state.ts
import { computed, signal, Signal } from '@angular/core';

export type SortDirection = 'asc' | 'desc';

export interface SortState<F extends string> {
  field: Signal<F>;
  dir: Signal<SortDirection>;
  /** `${field}_${dir}` token shared with the backend sort contract. */
  token: Signal<string>;
  toggle(field: F): void;
  isActive(field: F): boolean;
}

// Clicking the active column flips direction; clicking a new column selects it
// with a sensible default — ascending for text columns, descending otherwise.
export function createSortState<F extends string>(
  initialField: F,
  initialDir: SortDirection,
  textFields: readonly F[] = [],
): SortState<F> {
  const field = signal<F>(initialField);
  const dir = signal<SortDirection>(initialDir);
  const textSet = new Set<F>(textFields);

  return {
    field,
    dir,
    token: computed(() => `${field()}_${dir()}`),
    toggle(next: F): void {
      if (field() === next) {
        dir.update((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        field.set(next);
        dir.set(textSet.has(next) ? 'asc' : 'desc');
      }
    },
    isActive(candidate: F): boolean {
      return field() === candidate;
    },
  };
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npm test -- --include "**/sort-state.spec.ts"`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/core/utils/sort-state.ts frontend/src/app/core/utils/sort-state.spec.ts
git commit -m "feat(core): add createSortState signal helper for table sorting"
```

---

### Task 5: `sortItems` client-side comparator util

**Files:**
- Create: `frontend/src/app/core/utils/sort-items.ts`
- Test: `frontend/src/app/core/utils/sort-items.spec.ts`

(Foundation for Phase 2 client-side sorting; built and tested now.)

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/app/core/utils/sort-items.spec.ts
import { describe, expect, it } from 'vitest';
import { sortItems } from './sort-items';

interface Row { id: string; n: number | null; s: string | null; }

describe('sortItems', () => {
  it('sorts numbers ascending and descending', () => {
    const rows: Row[] = [{ id: 'a', n: 3, s: null }, { id: 'b', n: 1, s: null }];
    expect(sortItems(rows, (r) => r.n, 'asc').map((r) => r.id)).toEqual(['b', 'a']);
    expect(sortItems(rows, (r) => r.n, 'desc').map((r) => r.id)).toEqual(['a', 'b']);
  });

  it('sorts strings case-insensitively', () => {
    const rows: Row[] = [{ id: 'z', n: 0, s: 'zeta' }, { id: 'a', n: 0, s: 'Alpha' }];
    expect(sortItems(rows, (r) => r.s, 'asc').map((r) => r.id)).toEqual(['a', 'z']);
  });

  it('places null/empty values last regardless of direction', () => {
    const rows: Row[] = [{ id: 'x', n: null, s: null }, { id: 'y', n: 5, s: 'hi' }];
    expect(sortItems(rows, (r) => r.n, 'asc').map((r) => r.id)).toEqual(['y', 'x']);
    expect(sortItems(rows, (r) => r.n, 'desc').map((r) => r.id)).toEqual(['y', 'x']);
  });

  it('does not mutate the input array', () => {
    const rows: Row[] = [{ id: 'a', n: 2, s: null }, { id: 'b', n: 1, s: null }];
    sortItems(rows, (r) => r.n, 'asc');
    expect(rows.map((r) => r.id)).toEqual(['a', 'b']);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm test -- --include "**/sort-items.spec.ts"`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/src/app/core/utils/sort-items.ts
import { SortDirection } from './sort-state';

type Comparable = string | number | Date | null | undefined;

function isMissing(v: Comparable): boolean {
  return v === null || v === undefined || v === '';
}

function normalize(v: Comparable): string | number {
  if (v instanceof Date) return v.getTime();
  if (typeof v === 'string') return v.toLowerCase();
  return v as number;
}

// Pure comparator for fully-loaded client-side lists. Null/empty values sort
// to the bottom regardless of direction; strings compare case-insensitively.
export function sortItems<T>(
  items: readonly T[],
  accessor: (item: T) => Comparable,
  dir: SortDirection,
): T[] {
  const present: T[] = [];
  const missing: T[] = [];
  for (const item of items) {
    (isMissing(accessor(item)) ? missing : present).push(item);
  }
  const factor = dir === 'asc' ? 1 : -1;
  present.sort((a, b) => {
    const av = normalize(accessor(a));
    const bv = normalize(accessor(b));
    if (av < bv) return -1 * factor;
    if (av > bv) return 1 * factor;
    return 0;
  });
  return [...present, ...missing];
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npm test -- --include "**/sort-items.spec.ts"`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/core/utils/sort-items.ts frontend/src/app/core/utils/sort-items.spec.ts
git commit -m "feat(core): add sortItems client-side comparator util"
```

---

### Task 6: `SortableHeaderComponent`

**Files:**
- Create: `frontend/src/app/core/components/sortable-header/sortable-header.component.ts`
- Create: `frontend/src/app/core/components/sortable-header/index.ts` (re-export)
- Test: `frontend/src/app/core/components/sortable-header/sortable-header.component.spec.ts`

- [ ] **Step 1: Write the failing test**

```ts
// sortable-header.component.spec.ts
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';
import { createSortState } from '../../utils/sort-state';
import { SortableHeaderComponent } from './sortable-header.component';

type F = 'match' | 'title';

@Component({
  standalone: true,
  imports: [SortableHeaderComponent],
  template: `<table><thead><tr>
    <th appSortHeader [state]="state" field="match">Match</th>
    <th appSortHeader [state]="state" field="title">Title</th>
  </tr></thead></table>`,
})
class HostComponent {
  state = createSortState<F>('match', 'desc', ['title']);
}

describe('SortableHeaderComponent', () => {
  it('marks the active column with aria-sort and toggles on click', () => {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    const ths: HTMLTableCellElement[] = Array.from(
      fixture.nativeElement.querySelectorAll('th'),
    );
    expect(ths[0].getAttribute('aria-sort')).toBe('descending');
    expect(ths[1].getAttribute('aria-sort')).toBe('none');

    ths[0].querySelector('button')!.click();
    fixture.detectChanges();
    expect(ths[0].getAttribute('aria-sort')).toBe('ascending');

    ths[1].querySelector('button')!.click();
    fixture.detectChanges();
    expect(ths[1].getAttribute('aria-sort')).toBe('ascending'); // text default asc
    expect(ths[0].getAttribute('aria-sort')).toBe('none');
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm test -- --include "**/sortable-header.component.spec.ts"`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```ts
// sortable-header.component.ts
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { SortState } from '../../utils/sort-state';

@Component({
  selector: 'th[appSortHeader]',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" class="sort-header" (click)="state().toggle(field())">
      <ng-content />
      <span class="sort-arrow" aria-hidden="true">{{ arrow() }}</span>
    </button>
  `,
  styles: [`
    .sort-header {
      display: inline-flex; align-items: center; gap: 0.25rem;
      background: none; border: none; padding: 0; cursor: pointer;
      font: inherit; color: inherit;
    }
    .sort-arrow { font-size: 0.7em; opacity: 0.8; min-width: 0.7em; }
  `],
  host: { '[attr.aria-sort]': 'ariaSort()' },
})
export class SortableHeaderComponent {
  // The field key this header sorts by, and the shared sort state instance.
  readonly field = input.required<string>();
  readonly state = input.required<SortState<string>>();

  protected readonly active = computed(() => this.state().isActive(this.field()));
  protected readonly arrow = computed(() =>
    this.active() ? (this.state().dir() === 'asc' ? '▲' : '▼') : '',
  );
  protected readonly ariaSort = computed(() =>
    this.active() ? (this.state().dir() === 'asc' ? 'ascending' : 'descending') : 'none',
  );
}
```

```ts
// frontend/src/app/core/components/sortable-header/index.ts
export { SortableHeaderComponent } from './sortable-header.component';
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npm test -- --include "**/sortable-header.component.spec.ts"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/core/components/sortable-header/
git commit -m "feat(core): add SortableHeaderComponent for clickable table sorting"
```

---

### Task 7: Widen `JobFilters.sort` token type

**Files:**
- Modify: `frontend/src/app/pages/ingestion/models/job-filters.model.ts:12`

- [ ] **Step 1: Replace the `sort` field type**

```ts
  sort?:
    | 'match_asc' | 'match_desc'
    | 'posted_asc' | 'posted_desc'
    | 'title_asc' | 'title_desc'
    | 'company_asc' | 'company_desc'
    | 'location_asc' | 'location_desc'
    | 'source_asc' | 'source_desc'
    | 'date_desc'; // retained alias for backward compatibility
```

- [ ] **Step 2: Verify the build type-checks**

Run: `cd frontend && npm run build`
Expected: build succeeds (no type errors). If `onSortChange`'s cast in the component still references the old union it will error — that code is removed in Task 8, so run this verification again at the end of Task 8 if it fails here.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/ingestion/models/job-filters.model.ts
git commit -m "feat(ingestion): widen JobFilters.sort to the full token union"
```

---

### Task 8: Wire clickable headers into the ingestion component

**Files:**
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.ts` (lines 1, 14-16 imports; 100-101 sort signal; 134 loadJobs token; 291-296 handler)
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.html:123-166`

- [ ] **Step 1: Update the component TypeScript**

Add imports near the existing component imports (line 14 area):
```ts
import { SortableHeaderComponent } from '../../core/components/sortable-header';
import { createSortState } from '../../core/utils/sort-state';
```

Add `SortableHeaderComponent` to the `imports:` array of the `@Component` decorator.

Replace the sort signal (line 101):
```ts
  // Sort
  sortMode = signal<'' | 'match_desc' | 'date_desc'>('');
```
with:
```ts
  // Sort — clickable column headers, default Match descending.
  sort = createSortState<'match' | 'title' | 'company' | 'location' | 'source' | 'posted'>(
    'match',
    'desc',
    ['title', 'company', 'location', 'source'],
  );
```

Replace the token line in `loadJobs` (line 134):
```ts
    const filtersWithSort = { ...this.filters(), sort: this.sortMode() || undefined };
```
with:
```ts
    const filtersWithSort = { ...this.filters(), sort: this.sort.token() as JobFilters['sort'] };
```

Replace the `onSortChange` handler (lines 291-296):
```ts
  onSortChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value as '' | 'match_desc' | 'date_desc';
    this.sortMode.set(value);
    this.page.set(1);
    this.loadJobs();
  }
```
with:
```ts
  onSortColumn(field: 'match' | 'title' | 'company' | 'location' | 'source' | 'posted'): void {
    this.sort.toggle(field);
    this.page.set(1);
    this.loadJobs();
  }
```

- [ ] **Step 2: Update the template**

In `ingestion.component.html`, remove the sort `<select>` from the sort-bar (lines 126-131), keeping the "Show closed" toggle. The sort-bar block becomes:
```html
  <!-- Sort bar -->
  @if (jobs().length > 0) {
    <div class="sort-bar">
      <label class="toggle-label">
        <input
          type="checkbox"
          [checked]="includeClosed()"
          (change)="onIncludeClosedChange($event)"
          class="toggle-checkbox"
        />
        Show closed
      </label>
    </div>
  }
```

Replace the `<thead>` header row (lines 158-166) with sortable headers (Actions stays plain):
```html
        <thead>
          <tr>
            <th appSortHeader [state]="sort" field="match" (click)="onSortColumn('match')">Match</th>
            <th appSortHeader [state]="sort" field="title" (click)="onSortColumn('title')">Title</th>
            <th appSortHeader [state]="sort" field="company" (click)="onSortColumn('company')">Company</th>
            <th appSortHeader [state]="sort" field="location" (click)="onSortColumn('location')">Location</th>
            <th appSortHeader [state]="sort" field="source" (click)="onSortColumn('source')">Source</th>
            <th appSortHeader [state]="sort" field="posted" (click)="onSortColumn('posted')">Posted</th>
            <th>Actions</th>
          </tr>
        </thead>
```

Note: the component's `onSortColumn` drives the reload (page reset + `loadJobs`); the `SortableHeaderComponent`'s internal button also calls `state.toggle`, so to avoid a double-toggle the host `(click)` here must be the single source of truth. To prevent the inner button from toggling twice, the component handler calls `toggle` — but the inner button ALSO calls `toggle`. **Resolve this in Step 3.**

- [ ] **Step 3: Resolve the double-toggle — let the component own the reload, the header own the state**

The cleanest split: the `SortableHeaderComponent` button toggles the shared state (visual arrow updates instantly), and the ingestion component only needs to react (reset page + reload) — it must NOT toggle again. Change the template headers to drop the extra `(click)="onSortColumn(...)"` and instead listen for state changes via an output. Update `SortableHeaderComponent` to emit after toggling:

In `sortable-header.component.ts`, add an output and emit in the click handler:
```ts
import { ..., output } from '@angular/core';
// inside the class:
readonly sorted = output<void>();
```
Change the template button to:
```ts
    <button type="button" class="sort-header" (click)="onClick()">
```
and add:
```ts
  protected onClick(): void {
    this.state().toggle(this.field());
    this.sorted.emit();
  }
```

Then the ingestion headers become:
```html
            <th appSortHeader [state]="sort" field="match" (sorted)="onSorted()">Match</th>
            <th appSortHeader [state]="sort" field="title" (sorted)="onSorted()">Title</th>
            <th appSortHeader [state]="sort" field="company" (sorted)="onSorted()">Company</th>
            <th appSortHeader [state]="sort" field="location" (sorted)="onSorted()">Location</th>
            <th appSortHeader [state]="sort" field="source" (sorted)="onSorted()">Source</th>
            <th appSortHeader [state]="sort" field="posted" (sorted)="onSorted()">Posted</th>
            <th>Actions</th>
```
and replace `onSortColumn` in the component with:
```ts
  onSorted(): void {
    this.page.set(1);
    this.loadJobs();
  }
```
Update the `SortableHeaderComponent` spec from Task 6: clicking the button still toggles state (the existing assertions hold); optionally add `expect` on the `sorted` output via a host listener — not required for the test to pass.

- [ ] **Step 4: Run the frontend build + ingestion specs**

Run: `cd frontend && npm run build && npm test -- --include "**/sortable-header.component.spec.ts" --include "**/sort-state.spec.ts"`
Expected: build succeeds; specs PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/ingestion/ingestion.component.ts frontend/src/app/pages/ingestion/ingestion.component.html frontend/src/app/core/components/sortable-header/sortable-header.component.ts frontend/src/app/core/components/sortable-header/sortable-header.component.spec.ts
git commit -m "feat(ingestion): clickable column-header sorting on the jobs table"
```

---

### Task 9: Full verification

- [ ] **Step 1: Backend suite + lint**

Run: `cd backend && uv run python -m pytest tests/unit/ingestion -q && uv run ruff check .`
Expected: all PASS, no lint errors.

- [ ] **Step 2: Frontend build + full test run**

Run: `cd frontend && npm run build && npm test`
Expected: build succeeds; all specs PASS.

- [ ] **Step 3: Manual smoke (optional, needs DB)**

Run backend (`uv run app`) + frontend (`npm start`), open the ingestion page, click each column header, confirm the arrow toggles and the list reorders (and re-queries page 1). Confirm "Show closed" still works.

- [ ] **Step 4: Final commit if any fixups were needed**

```bash
git add -A && git commit -m "test(ingestion): verify Phase 1 sorting end to end"
```

---

## Self-review notes

- **Spec coverage:** Backend resolver (Task 1), `filter_and_paginate` integration (Task 2), API whitelist + match re-sort (Task 3), `createSortState` (Task 4), `sortItems` (Task 5), `SortableHeaderComponent` (Task 6), token type (Task 7), ingestion UI wiring (Task 8). Phase-1 spec items all mapped.
- **`date_desc` alias:** preserved in `_ALIASES` (BE) and the `JobFilters.sort` union (FE).
- **Default = Match desc:** `createSortState('match', 'desc', …)` + API default — preserved.
- **Double-toggle pitfall:** explicitly resolved in Task 8 Step 3 (header owns state via its button; component reacts via the `sorted` output — no second `toggle`).
- **`sortItems` consumption:** built in Phase 1 as foundation; first consumed by Phase 2 bare-list pages (documented as such).

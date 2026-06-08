# List Sorting & Filtering — Phase 2 (Client-side bare lists) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add client-side sorting + filtering to the Applications, Tracking, and Interview Stories list views, reusing the Phase 1 foundation (`createSortState`, `sortItems`, `SortableHeaderComponent`).

**Architecture:** Each page already loads its full collection into a signal. We add (a) a `createSortState` instance, (b) optional text/select filter signals, and (c) a `visibleX = computed(...)` that filters then sorts via `sortItems`. The template iterates the computed and uses `SortableHeaderComponent` headers — no `(sorted)` handler and no extra network call, because the computed re-derives from the sort signals automatically. Builds on `feat/list-sorting-filtering` (Phase 1).

**Tech Stack:** Angular 21 standalone + signals, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-07-sorting-filtering-design.md` (Phase 2 section).

---

### Task 1: Applications — sortable headers + status filter + text search

**Files:**
- Modify: `frontend/src/app/pages/applications/applications.component.ts`
- Modify: `frontend/src/app/pages/applications/applications.component.html`
- Test: `frontend/src/app/pages/applications/applications.component.spec.ts` (create)

**Design:**
- `sort = createSortState<'title'|'company'|'status'|'match'|'created'>('created','desc',['title','company','status'])`.
- `query = signal('')` (title/company text search), `statusFilter = signal('')`.
- Accessor map: title→`title`, company→`company`, status→`status`, match→`latest_match_score`, created→`created_at`.
- `visibleApplications = computed(...)`: filter by `query` (title/company substring, case-insensitive) and `statusFilter` (exact), then `sortItems`.
- Template: iterate `visibleApplications()`; headers Title/Company/Status/Match/Created use `appSortHeader`; Artifacts + actions stay plain. Add a filter bar (text input + status `select`) in the page header. Status options derived from the data: a `statuses = computed(() => [...new Set(applications().map(a => a.status))].sort())`.
- Spec: load 3 rows, assert default order by created desc; set `query`, assert filtered; toggle the status header twice, assert reorder.

### Task 2: Tracking — sortable headers + text search (keep existing status filter)

**Files:**
- Modify: `frontend/src/app/pages/tracking/tracking.component.ts`
- Modify: `frontend/src/app/pages/tracking/tracking.component.html`
- Test: `frontend/src/app/pages/tracking/tracking.component.spec.ts` (create)

**Design:**
- Keep the existing server-side `statusFilter`/`onStatusFilterChange` (re-queries) untouched.
- `sort = createSortState<'company'|'title'|'status'|'posted'|'applied'>('company','asc',['company','title','status'])`.
- `query = signal('')` (company/title search).
- Accessor map: company→`company`, title→`title`, status→`status`, posted→`posted_date`, applied→`applied_at`.
- `visibleApplications = computed(...)`: filter by `query`, then `sortItems` over `applications()`.
- Template: iterate `visibleApplications()`; headers Company/Title/Status/Posted/Applied use `appSortHeader`; Location/Salary/Source/Notes/Actions stay plain. Add a company/title text input next to the existing status `select` in the header actions.
- Spec: load 3 rows; assert company asc default; toggle posted header, assert order by posted_date; set query, assert filter.

### Task 3: Interview Stories — sortable headers + competency filter

**Files:**
- Modify: `frontend/src/app/pages/interview/interview.component.ts`
- Modify: `frontend/src/app/pages/interview/interview.component.html`
- Test: `frontend/src/app/pages/interview/interview.component.spec.ts` (create, scoped to the story bank)

**Design:**
- `storySort = createSortState<'title'|'competency'|'created'>('created','desc',['title','competency'])`.
- `competencyFilter = signal<Competency | ''>('')`.
- Accessor map: title→`title`, competency→`competency`, created→`created_at`.
- `visibleStories = computed(...)`: filter by `competencyFilter` (exact), then `sortItems` over `stories()`.
- Template (story bank table only): iterate `visibleStories()`; headers Title/Competency/Created use `appSortHeader`; Situation/Actions stay plain. Add a competency `select` (reuse `competencyOptions`) above the table. Note: the table currently has no Created column header — add a "Created" `<th>`/`<td>` (value `created_at | date:'mediumDate'`) so the created sort is visible.
- Spec: load 3 stories; assert created desc default; set competencyFilter, assert filtered; toggle title header, assert order.

### Task 4: Verification

- [ ] `cd frontend && npm run build` — succeeds.
- [ ] `cd frontend && npm test` — all specs pass (including 3 new).
- [ ] Commit per task; final verification commit if needed.

---

## Self-review notes

- All three pages keep their existing create/delete/research/evaluate logic untouched — only display derivation changes (iterate the computed instead of the raw signal).
- No backend changes (bare lists). No new network calls from sorting.
- Reuses Phase 1 foundation verbatim; `(sorted)` output intentionally unused for client-side pages.

# List Sorting & Filtering — Phase 3 (Remaining views) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Extend sorting/filtering to the remaining list views — Cover Letter Library, Cover Letter Templates, Admin Usage Breakdown, Outreach events (client-side), plus Autohunt digests and Admin Recent Calls (server-side, limit/offset endpoints).

**Architecture:** Two UI shapes. **Tables** (Admin Breakdown, Admin Recent Calls) reuse `SortableHeaderComponent` clickable headers. **Lists/`<ul>`** (Cover Letters, Templates, Outreach, Autohunt) get a small sort `<select>` bound to a `createSortState` instance via the new `set(field, dir)` method (`[value]="sort.token()"`, `(change)` parses `<field>_<dir>` and calls `set`). Client-side views derive a `visibleX = computed(...)` using `sortItems`; server-side views (Autohunt, Admin Recent Calls) send a `sort` token to the backend, which whitelists it and applies `ORDER BY` in the repository.

**Tech Stack:** Angular 21 signals + Vitest; FastAPI/SQLAlchemy + pytest.

**Foundation added this phase:** `SortState.set(field, dir)` (done, tested) enables dropdown-driven sorting.

**Spec:** `docs/superpowers/specs/2026-06-07-sorting-filtering-design.md` (Phase 3 section).

---

### Task 1: Cover Letter Library (client-side, list) — sort dropdown
**Files:** `frontend/src/app/pages/profile/components/cover-letter-library/cover-letter-library.component.ts` + `.html`
- `sort = createSortState<'created'|'company'|'title'>('created','desc',['company','title'])`.
- Change `filtered` computed to filter by `query` (unchanged) then `sortItems` by the active field (created→`created_at`, company→`company`, title→`title`).
- Template: add a `<select>` in `.library-header` with options Newest (`created_desc`), Oldest (`created_asc`), Company A–Z (`company_asc`), Title A–Z (`title_asc`); `(change)="onSortSelect($event)"` parses token → `sort.set`.

### Task 2: Cover Letter Templates (client-side, list) — sort dropdown + filters
**Files:** `cover-letter-templates.component.ts` + `.html`
- `sort = createSortState<'updated'|'name'|'tone'|'language'>('updated','desc',['name','tone','language'])`.
- `toneFilter`/`languageFilter` signals (optional, exact match).
- `visibleTemplates = computed(...)`: filter then `sortItems` (updated→`updated_at`, name→`name`, tone→`tone`, language→`language`).
- Template: sort `<select>` (Recently updated / Name A–Z / Tone / Language) near the list header; iterate `visibleTemplates()`.

### Task 3: Admin Usage Breakdown (client-side, table) — clickable headers
**Files:** `admin-usage.component.ts` + `.html`
- `breakdownSort = createSortState<'key'|'calls'|'total_tokens'|'cost_usd'>('cost_usd','desc',['key'])`.
- `visibleBuckets = computed(...)`: `sortItems` over the current breakdown `buckets` (no filter).
- Template: breakdown table headers (Dimension/Calls/Tokens/Cost) use `appSortHeader [state]="breakdownSort"`; iterate `visibleBuckets()`. Share column stays plain.

### Task 4: Outreach events (client-side, list) — sort toggle + kind filter
**Files:** `outreach.component.ts` + `.html`
- `eventSort = createSortState<'created'>('created','desc')`; `kindFilter = signal<OutreachEventKind|''>('')`.
- `visibleEvents = computed(...)`: filter by kind, then `sortItems` by `created_at` (replaces the current `.reverse()`; keep storing events in natural order, sort in the computed).
- Template: add Newest/Oldest `<select>` + kind `<select>` above the timeline; iterate `visibleEvents()`.

### Task 5: Autohunt digests (server-side, list)
**Backend** `autohunt`:
- Add `sort` query param to `GET /autohunt/digests` (allowed: `created_desc|created_asc|count_desc|count_asc`, default `created_desc`).
- Thread through `AutoHuntService.list_recent(limit, sort)` → `DigestRepository.list_recent(limit, sort)`; map field→column (`created`→`created_at`, `count`→`job_count`), apply `.order_by(col.desc()/asc())`. Unknown → default.
- Tests: `tests/unit/autohunt/` repo/route test for each sort option + default.
**Frontend:**
- `autohunt.service.ts` `listRecent(limit, sort?)` sends `sort`.
- `autohunt.component.ts`: `historySort = createSortState<'created'|'count'>('created','desc')`; on change re-call `loadHistory()` with the token. Template: sort `<select>` above the history `<ul>`.

### Task 6: Admin Recent Calls (server-side, table)
**Backend** `admin`:
- Add `sort` query param to `GET /admin/usage/calls` (allowed: `{created,cost,latency,input_tokens,output_tokens}_{asc,desc}`, default `created_desc`).
- Thread through `UsageAggregator.recent_calls(..., sort)` → `LLMUsageLogRepository.list_recent(..., sort)`; field→column map, `.order_by`. Unknown → default.
- Tests: repo/route tests for representative sorts + default + invalid-fallback.
**Frontend:**
- `admin-usage.service.ts` `recentCalls` filters gains `sort`.
- `admin-usage.component.ts`: `callsSort = createSortState<...>('created','desc',[])`; clickable headers on the calls table that set sort + re-call `loadRecent()`. (Time/Cost/Latency/In/Out sortable; Feature/Provider/Model/Status stay plain or filtered as today.)

### Task 7: Verification
- [ ] `cd backend && uv run python -m pytest -q && uv run ruff check .`
- [ ] `cd frontend && npm run build && npm test`
- [ ] Commit per task.

---

## Self-review notes
- List views use a sort `<select>` (no table headers to click); tables reuse `SortableHeaderComponent`. Both bind to `createSortState`.
- Server-side endpoints validate the `sort` token against a whitelist and fall back to the existing default — same contract as Phase 1's ingestion endpoint. No new DB columns/migrations (all sort columns already exist and are mostly indexed).
- Cover Letter Library keeps its existing search; Outreach keeps nudges/compose untouched.

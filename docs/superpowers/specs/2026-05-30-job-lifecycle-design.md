# Job Lifecycle: Change Detection & Closure Detection

**Date:** 2026-05-30
**Status:** Design — approved, pending spec review
**Bucket scope:** both `boards` and `portals`

## Problem

On refetch, HireSense neither detects closed jobs nor updates jobs it already
has. Today `JobsRepository.add_if_absent` does a pure existence check on a
content-derived `dedup_key` (`sha256(source:title:company:url)`):

- **Closed jobs are never detected.** A closed posting just stops appearing in
  a source's fetch results, but the stored row persists until age-based pruning
  (`prune_older_than`, by `fetched_at`) deletes it — regardless of whether it is
  still live. `fetched_at` is set once at insert and never refreshed, so a
  still-open job first seen long ago gets age-pruned while live.
- **Changes to existing jobs are ignored.** `add_if_absent` never compares or
  updates fields. Worse, because `dedup_key` hashes `title`+`url`, an edit to
  either is seen as a brand-new job — a duplicate — and the original looks like
  it "disappeared."
- **`source_id` is dropped.** `RawJobListing` carries each source's stable
  native ID, but `IngestedJob` has no `source_id` column, so the one field that
  would give a posting a stable identity is discarded at persistence.
- **The vector index has no removal path.** `JobEmbeddingIndexer` only
  `upsert`s. Pruned/closed jobs stay in the vector store and surface in semantic
  search as ghosts.

## Goals

Equal-weight delivery of:

1. **Change detection** — re-ingesting an existing posting updates it in place
   (and re-embeds it) instead of skipping or duplicating.
2. **Closure detection** — determine when a posting is no longer open, mark it
   `closed` (keep the row + badge), and drop it from semantic search.

Coverage should be as complete as practical, acknowledging that many closed
postings keep a live URL, so HTTP status alone is insufficient.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | Both change + closure detection, equal weight |
| Closed-job handling | Mark `status=closed`, keep row + badge, drop from search |
| Default visibility | Hidden by default + "Show closed" toggle |
| Detection mechanism | Layered: inline disappearance (snapshot sources) + throttled URL-probe sweep with content markers (feed/search sources) + age backstop |
| Identity | Persist `source_id`; identity = `(bucket, source, source_id)` with `url` fallback; Alembic migration |
| Revalidation cadence | Disappearance inline during ingestion; URL probe = separate throttled scheduled sweep |
| Architecture | Approach A — shared-repository upsert + per-adapter snapshot-capability flag, phased rollout |

## Architecture (Approach A)

Centralize lifecycle on `JobsRepository` so both fetch loops
(`IngestionOrchestrator` for `boards`, `PortalScanner` for `portals`) share
identical logic and cannot drift. Adapters declare a
`supports_snapshot_closure()` capability. Deliver in two phases:

- **Phase 1 (no new network):** `source_id` migration, identity-keyed upsert,
  change detection, inline disappearance for snapshot sources, status/badge/
  visibility, index removal on close.
- **Phase 2 (network):** throttled `JobRevalidationService` URL-probe sweep
  with closed-content markers, scheduled independently.

Phase 1 delivers change detection everywhere plus reliable closures for the
portals with zero new network risk. Phase 2 layers feed/search closure coverage
on top without touching Phase 1's hot path.

## Section 1: Data model & migration

Add columns to `IngestedJob` (`ingested_jobs`):

| Column | Type | Purpose |
|---|---|---|
| `source_id` | `String(255)`, nullable | Source's native ID (from `RawJobListing`, currently dropped). |
| `identity_key` | `String(64)`, not null | Stable identity for uniqueness/lookup: `source_id` when present, else `sha256(url)`. |
| `status` | `String(10)`, default `"open"` | `"open"` or `"closed"`. |
| `content_hash` | `String(64)` | sha256 of mutable fields — drives change detection. |
| `last_seen_at` | `DateTime(tz)`, default now | Last fetch that still contained it; bumped on every sighting. |
| `last_checked_at` | `DateTime(tz)`, nullable | Last URL-probe time (Phase 2 sweep ordering). |
| `closed_at` | `DateTime(tz)`, nullable | When marked closed. |
| `updated_at` | `DateTime(tz)`, nullable | Last in-place field update. |
| `missed_count` | `Integer`, default 0 | Consecutive snapshot fetches missing it (disappearance grace). |

The existing `fetched_at` is retained as "first seen" (semantics unchanged).

**Identity** = `(bucket, source, identity_key)`, where `identity_key =
source_id` when the source supplies one, else `sha256(url)`. Collapsing both
cases into one fixed-width `identity_key` column avoids a unique index on the
2048-char `url` (which can exceed Postgres's btree row-size limit) and keeps a
single uniqueness rule instead of two conditional indexes. The old
content-based `dedup_key` is replaced by `identity_key` for uniqueness;
`content_hash` carries the "did it change?" role that `dedup_key` previously
conflated.

**Migration (Alembic, run via `uv run python -m alembic`):**

- Add the columns above.
- Backfill: `status="open"`; `content_hash` computed from current fields;
  `last_seen_at = fetched_at`; `source_id = NULL` for existing rows (we never
  stored it); `identity_key = sha256(url)` for every existing row (url-identity,
  acceptable since `source_id` is unavailable historically).
- New unique index: `(bucket, source, identity_key)`.
- Drop the old `ux_ingested_jobs_bucket_dedup` constraint / `dedup_key` column.

## Section 2: Upsert & change detection (write path)

Replace `JobsRepository.add_if_absent()` with
**`upsert(job) -> UpsertResult`** where `UpsertResult ∈ {INSERTED, UPDATED,
UNCHANGED}`:

1. Look up the row by identity `(bucket, source, identity_key)`.
2. **Not found** → insert; `status=open`,
   `first_seen (fetched_at) = last_seen_at = now`, `content_hash=H`.
   → `INSERTED`.
3. **Found** → always set `last_seen_at=now`, `missed_count=0`; if it was
   `closed`, flip to `open` and clear `closed_at` (re-listed). Then:
   - `content_hash` differs → update all mutable fields, set `updated_at=now`,
     **keep the same row `id`**. → `UPDATED`.
   - same → `UNCHANGED`.

`content_hash(job)` is a pure helper over title + company + description +
location + salary_range + sorted skills.

Critical change vs. today: ingestion currently generates a fresh `uuid` per run
and skips existing rows. Under upsert the existing row `id` is **reused** on
update, so the vector-store entry (keyed by `id`) updates in place rather than
orphaning. Both `IngestionOrchestrator.run()` and `PortalScanner` call
`upsert()`. `INSERTED` and `UPDATED` jobs are collected for (re-)indexing;
`UNCHANGED` are skipped.

## Section 3: Disappearance detection (Phase 1, inline, snapshot sources)

Add `supports_snapshot_closure() -> bool` to the adapter protocol — default
`False`; `True` for `greenhouse`/`lever`/`ashby`. A pure domain helper
`ClosureDetector` decides what to close.

Per source, after a successful fetch:

1. **Safety gate** — run disappearance only if the source
   `supports_snapshot_closure()` **and** the fetch **succeeded** (did not
   raise). A fetch that errored is already caught + `continue`d, so it never
   reaches the detector. An *empty but successful* fetch from a snapshot source
   IS a valid signal (a company board can legitimately drop to zero open
   roles), so it is allowed to drive closure — the miss-threshold below, not an
   empty-result gate, is what guards against a transient/soft-error empty
   response. (An empty-result gate would make the last open role of any board
   un-closeable, which is wrong.)
2. Build the set of identities seen this run. For each stored **open** job of
   that `(bucket, source)` not in the seen set → `missed_count += 1`; for seen
   ones → `missed_count = 0`.
3. When `missed_count >= JOB_CLOSURE_MISS_THRESHOLD` (default `2`) → mark closed.
   The threshold absorbs a single flaky/partial fetch before declaring death.

Non-snapshot sources (remotive, remoteok, jobicy, himalayas, weworkremotely,
getonboard, linkedin) get no disappearance logic — they rely on Phase 2 + age
backstop. `hn_hiring` is special: its URLs are frozen HN comments that never
404 and have no closed marker, so HN closure is age/month-rollover-based via the
backstop, not probed.

## Section 4: Closed-job handling (status → index → API → frontend)

**Index removal.** Add `JobEmbeddingIndexer.remove(job_ids)` and a `remove`
method on the vector-store port. On close → remove from the vector store (drops
it from semantic ranking, fixing the existing ghost-in-search bug). On re-open
(Section 2 step 3) → re-index.

**API / filtering.** Add `include_closed: bool = False` to `JobQueryParams`. In
`filter_and_paginate`, drop `status == "closed"` unless `include_closed`.
Semantic search **always** excludes closed regardless of the flag. The
job-detail endpoint still returns a closed job (so a tracked job stays
reachable), with `status` in the payload.

**Frontend.** The `NormalizedJob` API model gains `status`. The ingestion page
list:

- default view hides closed (`include_closed=false`);
- a **"Show closed"** toggle re-requests with `include_closed=true`;
- closed cards render a **"Closed"** badge and are visually de-emphasized.

**Age backstop.** Keep `prune_older_than` (hard delete) as the final GC,
coexisting with soft closure. Bump `INGESTION_JOB_RETENTION_DAYS` (30 → 90) so
explicit closure, not the age timer, is the primary lifecycle signal and closed
jobs linger long enough to stay useful with their badge.

## Section 5: URL-probe revalidation sweep (Phase 2, network, scheduled)

A new domain service `JobRevalidationService` plus a pure
`ClosedListingClassifier`.

**Selection.** Each run, pick open jobs from **non-snapshot** sources ordered by
`last_checked_at ASC NULLS FIRST` (oldest-checked first), capped at
`JOB_REVALIDATION_BATCH` per run — bounds cost, guarantees fair rotation.

**Probing.** `GET url` with timeout, throttled by a concurrency cap +
per-request delay (reuse the LinkedIn-style `detail_concurrency` /
`detail_delay` pattern). `ClosedListingClassifier` maps result →
`OPEN | CLOSED | UNKNOWN`:

- `404` / `410` / connection-gone → `CLOSED`.
- `200` **and** body matches a configured closed-marker phrase (e.g. "no longer
  accepting applications", "position has been filled", "this job is closed",
  "ya no está disponible") → `CLOSED` (the "URL stays alive after closing"
  case).
- otherwise → `OPEN`.

`OPEN`/`UNKNOWN` → set `last_checked_at=now` only (UNKNOWN never closes — no
action on ambiguity). `CLOSED` → mark closed + remove from index (Section 4).
The classifier is pure (status + body → verdict), unit-testable without network.

**Scheduling.** Runs as its own scheduled job, independent of the ingestion
cooldown; interval config-driven (`JOB_REVALIDATION_INTERVAL_HOURS`, default
daily). It does **not** run inside `IngestionOrchestrator.run()`.

## Section 6: Config & testing

**New config keys** (`config.py` + `.env.example`, with placeholders/comments;
no hardcoded values):

- `JOB_CLOSURE_MISS_THRESHOLD=2`
- `JOB_REVALIDATION_INTERVAL_HOURS=24`
- `JOB_REVALIDATION_BATCH=100`
- `JOB_REVALIDATION_CONCURRENCY` / `JOB_REVALIDATION_DELAY`
- `JOB_CLOSED_MARKERS=` (delimited phrase list)
- `INGESTION_JOB_RETENTION_DAYS` bumped 30 → 90

**Testing** (existing unit-test style; fakes for http/repo):

- `content_hash`: stability + change sensitivity.
- `JobsRepository.upsert`: insert / unchanged / changed (fields update, **id
  preserved**) / reopen-on-resight.
- `ClosureDetector`: miss-threshold gating; **empty/failed fetch never closes**;
  non-snapshot sources skipped; seen resets `missed_count`.
- `ClosedListingClassifier`: 404/410 → closed; 200+marker → closed; 200 plain →
  open; unknown → no-op (pure, no network).
- `JobRevalidationService`: oldest-first selection, batch cap, throttling, marks
  closed + calls index remove.
- `filter_and_paginate`: closed hidden by default; shown with `include_closed`;
  semantic search always excludes closed.
- `JobEmbeddingIndexer.remove`: closure drops vector entry; reopen re-indexes.
- Migration smoke: backfill leaves existing rows `open` with computed
  `content_hash`.

## Components & boundaries

| Component | Responsibility | Depends on |
|---|---|---|
| `IngestedJob` (ORM) + migration | Persist lifecycle fields | database |
| `content_hash()` | Pure mutable-field hash | — |
| `JobsRepository.upsert / mark_closed / reopen / find_open_stale` | Identity-keyed writes, closure state, sweep selection | session factory |
| `ClosureDetector` | Decide which stored jobs to close from a fetch | — (pure) |
| adapter `supports_snapshot_closure()` | Declare snapshot completeness | — |
| `JobEmbeddingIndexer.remove()` + vector-store `remove()` | Drop/re-add vectors on close/reopen | embedding, vector store |
| `JobQueryParams.include_closed` + `filter_and_paginate` | Default-hide closed; search always excludes | — |
| `ClosedListingClassifier` | Map (status, body) → verdict | — (pure) |
| `JobRevalidationService` | Throttled URL-probe sweep | http client, repo, classifier, indexer |
| Frontend status/badge/toggle | Surface closed state | API `status` |

## Out of scope

- Per-domain politeness beyond a global concurrency cap + delay.
- Notifying users when a tracked job closes or changes.
- Historical change log / diff history (only current state is kept).

# Per-job audit trail and ingestion run history

**Date:** 2026-08-19
**Status:** Approved, ready to implement

## Problem

A fetch reports `713 new job(s) ingested` and a sweep reports `427 listing(s) closed`,
and nothing in the system can say which jobs those were.

For a corpus of roughly 4,500 open jobs, 1,140 changes in one cycle is a large
fraction. The obvious question — are those 713 genuinely new listings, or the same
jobs the closure sweep just closed coming back because they are still in their
feeds? — is currently unanswerable. The data needed to answer it is discarded the
moment a run finishes:

- `SourceHealthTracker` is process-local. Per-source counts for the last run are
  lost on restart, and there is no history before that.
- `IngestedJob` carries `fetched_at`, `last_seen_at`, `last_checked_at` and
  `closed_at`, but only the *latest* value of each. A job that has opened and
  closed three times looks identical to one that opened once.
- `UpsertResult` (`INSERTED` / `UPDATED` / `REOPENED` / `UNCHANGED`) is computed on
  every upsert and then thrown away after driving the indexing decision.

The consequence is not only a missing feature. It blocks diagnosis: the closure
sweep classifies a dead-end redirect as CLOSED, and there is no way to check
whether that heuristic is over-closing, because the evidence is gone by the time
anyone asks.

## Approach

Three approaches were considered.

**A — repository writes history inline.** Emit rows inside `bulk_upsert`'s session
and each closure path, committing atomically with the change. History can never
disagree with the job table. Rejected because `jobs_repository.py` is already
~450 lines and would take on a second responsibility, and because every future
write path must remember to log or history silently goes incomplete.

**B — domain events on the existing `EventBus`.** Rejected. The in-memory bus is
fire-and-forget and non-transactional, so history would drop silently under
failure — a bad property for an audit trail. The old-to-new diff also only exists
inside the repository, so `_apply_to_row` would have to surface it regardless.
The decoupling is paid for and not delivered.

**C — repository surfaces the diff, a dedicated recorder persists it. Chosen.**
The diff is captured where it is already computed, auditing stays one focused unit
instead of leaking into persistence, and writes are one bulk insert per run rather
than per job — which matters at ~1,140 events per cycle.

**Accepted trade-off:** recording is *not* atomic with the upsert. A crash between
the job write and the history write loses that run's events. The job table remains
the source of truth; history is an audit of convenience. This was chosen
deliberately over approach A's atomicity.

## Design

### Schema

Two migrations on top of `044`.

`ingestion_runs`:

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `started_at` | timestamptz not null | |
| `finished_at` | timestamptz null | null while in flight |
| `trigger` | varchar(20) not null | `fetch`, `scheduler`, or `manual` |
| `status` | varchar(20) not null | `running`, `completed`, or `failed` |

`job_history_events`:

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `job_id` | varchar FK to `ingested_jobs.id`, ON DELETE CASCADE | |
| `run_id` | uuid FK to `ingestion_runs.id`, **nullable** | |
| `event` | varchar(20) not null | `inserted`, `updated`, `reopened`, `closed` |
| `changed_fields` | jsonb not null, default `{}` | see shape below |
| `reason` | varchar(40) null | closures only |
| `occurred_at` | timestamptz not null | |

Indexes: `(job_id, occurred_at DESC)` for the per-job timeline, `(run_id)` for
run drill-down, `(occurred_at)` for retention pruning.

`run_id` is nullable on purpose. Closures produced by the URL-probe revalidation
sweep do not belong to an ingestion run — the sweep is a separate, independently
scheduled process. Inventing a synthetic run to satisfy a NOT NULL constraint
would misrepresent when those closures happened and why.

`reason` values for closures: `probe_404`, `dead_end_redirect`, `expiry`,
`snapshot_disappearance`.

### Capturing the diff

`UpsertOutcome` (`src/hiresense/ingestion/ports/jobs_repository.py`) gains
`changed_fields: dict[str, ChangedValue]`, populated in
`JobsRepository._apply_to_row` (`infrastructure/jobs_repository.py:114`) — the one place where the existing ORM row (old
state) and the incoming `NormalizedJob` (new state) are both in scope.

Tracked with before/after values: `title`, `company`, `salary_range`, `location`,
`employment_type`. Serialised shape, one entry per field that actually differed:

```json
{
  "salary_range": {"old": null, "new": "$180-200K"},
  "title": {"old": "Engineer", "new": "Senior Engineer"},
  "description": {"changed": true}
}
```

`description` is tracked as a boolean changed/unchanged flag only. Descriptions
are large and frequently churn on whitespace and boilerplate; storing them
before-and-after would dominate the table for little analytical value.

Fields already excluded from `content_hash` (identity, timestamps, scores) are
excluded here too — an update to them is not a content change.

### Recording

`JobHistoryRecorder`, its own module behind `JobHistoryPort`, with one method:

```
record(run_id: str | None, events: list[JobHistoryEvent]) -> None
```

One bulk insert per call. Two callers:

- `IngestionOrchestrator` — opens a run before the source loop, records events
  built from each source's `outcomes` (skipping `UNCHANGED`), closes the run in
  its `finally` so a crashed pass is recorded as `failed` rather than left
  `running` forever.
- `JobRevalidationService` — records `closed` events with `run_id=None` and the
  probe-derived reason, in `_probe_and_close` and `_close_expired`.

Failures are logged and swallowed, never raised. History must not be able to fail
an ingestion pass. Each swallowed failure increments
`automation_failures_total{component=job_history_record}`, consistent with how
`JobEmbeddingIndexer` already handles its own non-fatal failures.

### Retention

Time-based, per the existing `INGESTION_JOB_RETENTION_DAYS` pattern. New
`JOB_HISTORY_RETENTION_DAYS` (default 90) prunes `job_history_events` on
`occurred_at`, folded into `IngestionOrchestrator._prune_expired` so it reuses the
pass that already runs each cycle. Runs whose events have all aged out are pruned
with them.

The FK cascade is a second, independent bound: deleting a job removes its history
regardless of age.

### API

- `GET /ingestion/jobs/{id}/history` — events for one job, newest first
- `GET /ingestion/runs` — paginated run list with per-run totals
- `GET /ingestion/runs/{id}` — one run, with per-source counts and its events

All three sit on the existing `require_auth` router.

### Frontend

- **Job detail timeline** — a vertical list under the existing detail panel:
  "Reopened 2 hours ago", "Salary changed 3 days ago — was blank, now $180-200K",
  "Closed 5 days ago (dead-end redirect)".
- **Runs page** — a table of recent runs (started, duration, trigger, totals), each
  row expanding to per-source counts and linking to the jobs it touched.

## Files

**New (backend)**
- `alembic/versions/045_create_ingestion_runs.py`
- `alembic/versions/046_create_job_history_events.py`
- `src/hiresense/ingestion/domain/job_history_event.py`
- `src/hiresense/ingestion/domain/job_history_recorder.py`
- `src/hiresense/ingestion/ports/job_history.py`
- `src/hiresense/ingestion/infrastructure/job_history_models.py`
- `src/hiresense/ingestion/infrastructure/job_history_repository.py`

**Modified (backend)**
- `ports/jobs_repository.py` — `changed_fields` on `UpsertOutcome`
- `infrastructure/jobs_repository.py` — populate the diff in `_apply_to_row`;
  register new ORM classes in `infrastructure/registry.py`
- `domain/services.py` — open/close the run, record outcomes, prune history
- `domain/job_revalidation_service.py` — record closures with reasons
- `api/routes.py`, `api/schemas.py` — three endpoints
- `composition/ingestion.py` — wire the recorder
- `shared/config/groups/ingestion.py` and `.env.example` — retention knob

**New (frontend)**
- `pages/jobs/job-history-timeline/` component
- `pages/admin/runs/` page and route
- `core/api/` client methods and `.model.ts` interfaces

## Testing

- **Diff capture** — `_apply_to_row` produces the expected `changed_fields` for
  each tracked field; description reduces to a flag; untracked field changes
  produce no entry.
- **Recorder** — `UNCHANGED` outcomes are skipped; one bulk insert per call; a
  failing store is swallowed and increments the failure metric.
- **Orchestrator** — a run is opened and closed; a crashed pass marks the run
  `failed`; events carry the run id.
- **Revalidation** — closures record `run_id=None` with the correct reason per
  closure path.
- **Retention** — events past the cutoff are pruned; recent ones survive; deleting
  a job cascades.
- **API** — the three endpoints return the expected shapes and enforce auth.
- **Frontend** — timeline renders each event type; runs page expands per-source
  counts.

Integration tests run against in-memory SQLite as usual. Any Postgres-specific
bulk-insert syntax should additionally be exercised against a live database via
the existing opt-in `pgvector`-marked pattern.

## Open question

Whether the first run after deploy should backfill a synthetic `inserted` event
for every existing job. Backfilling makes every job's timeline start somewhere
rather than appearing to spring into existence; not backfilling keeps the table
honest about what was actually observed.

Recommendation: **do not backfill.** An audit trail that fabricates events it did
not witness is worse than one with a known start date. Surface "History begins
2026-08-19" in the timeline empty state instead.

# Scheduler Foundation — Design (Autopilot Phase 1)

**Date:** 2026-06-21
**Initiative:** [HireSense Autopilot](./2026-06-21-autopilot-initiative.md) — Phase 1
**Status:** Approved for planning

## Goal

Let HireSense self-drive its recurring pipeline steps on a cadence,
**in-process**, behind a master switch, with observable run history — retiring
the external-cron requirement. The cron strings already present in `config.py`
become the real source of truth instead of being informational-only.

## Non-goals

- Multi-replica leader election (single-user deployment; documented limitation).
- Runtime-editable cadence / a full cron-editor UI (cadence stays config-driven;
  only enable/disable is runtime-togglable).
- Portal scan scheduling (needs default scan filters — deferred).
- Any outbound sending (outreach follow-ups are computed only, never sent — that
  is Phase 5).
- Chaining jobs into a pipeline (each job runs independently on its own cadence
  — chaining is Phase 4).

## Jobs to schedule

All four already exist as domain methods; the scheduler only invokes them.

| Job name | Calls | Cadence config | Notes |
|----------|-------|----------------|-------|
| `ingestion_fetch` | `IngestionOrchestrator.run()` | `ingestion_schedule` (`0 */6 * * *`) | Existing `IngestionCooldownError` → recorded as `skipped`. |
| `revalidation_sweep` | `JobRevalidationService.sweep()` | `job_revalidation_interval_hours` (24) | Interval trigger built from hours. |
| `autohunt_digest` | `AutoHuntService.run()` | `autohunt_schedule` (`0 9 * * *`) | Persists a `Digest`. |
| `outreach_followups` | `OutreachService.due_followups()` | `outreach_followup_schedule` (`0 10 * * *`) | **Compute only — no sending.** Surfaces due nudges for later phases. |

## Architecture

New `scheduler/` bounded-context module, layered `api → domain ← infrastructure`
like its siblings.

### `domain/`
- `JobStatus` — enum: `success` | `failure` | `skipped`.
- `JobRun` — pure Pydantic run-history record: `job_name`, `started_at`,
  `finished_at`, `status: JobStatus`, `detail: str | None` (error message or
  summary), `items_affected: int | None`, `duration_seconds: float | None`.
- `ScheduledJobView` — read model for the status API: `name`, `cron`, `enabled`,
  `last_run: JobRun | None`, `next_run_at: datetime | None`.
- A `JobRunRepository` Protocol (port): `record(run)`, `recent(job_name, limit)`,
  `latest(job_name)`, `prune(older_than)`.
- A `JobToggleRepository` Protocol (port): `is_enabled(job_name)`,
  `set_enabled(job_name, enabled)`, `all_states()`. Per-job enable/disable lives
  in the DB, seeded enabled on first read.

### `infrastructure/`
- `ApschedulerRunner` — wraps an APScheduler `AsyncIOScheduler`. Registers each
  named job with its trigger (cron or interval), `max_instances=1`,
  `coalesce=True`, and a misfire grace time. Exposes `start()`, `shutdown()`,
  `next_run_at(name)`, and `trigger_now(name)`.
- `JobRunOrm` + `JobRunRepositoryImpl` — SQLAlchemy persistence for run history.
- `JobToggleOrm` + `JobToggleRepositoryImpl` — per-job enabled flags.
- **Both ORM classes imported in `infrastructure/registry.py`** (else Alembic
  `--autogenerate` misses the tables).

### `api/`
- `GET /scheduler/jobs` → `list[ScheduledJobView]`.
- `GET /scheduler/jobs/{name}/runs?limit=` → recent `JobRun`s.
- `POST /scheduler/jobs/{name}/toggle` *(admin-gated)* → enable/disable.
- `POST /scheduler/jobs/{name}/run-now` *(admin-gated)* → invoke the same wrapped
  callable immediately, off the request thread.
- `dependencies.py` reads the provider back off `app.state`.

### `bootstrap/build_scheduler(...)`
Receives the already-built domain callables from `create_app` (ingestion
orchestrator, revalidation service, autohunt service, outreach service) plus the
`scheduler` infra (repos) and `Settings`. Assembles the job registry — a list of
`(name, callable, trigger, default_enabled)` — and returns a `Provider` stored on
`app.state.scheduler`. The runner is **started in the FastAPI lifespan** (which
today only tears down — a startup branch is added), and only when
`settings.scheduler_enabled` is true.

## Job wrapper (the core behavior)

Every scheduled invocation goes through one wrapper that:

1. Reads the job's enable-toggle; if disabled → record a `skipped` `JobRun` and
   return without invoking the callable.
2. Stamps `started_at`, invokes the async callable.
3. On success → record `success` with `items_affected` (e.g. jobs fetched,
   listings closed, digest entries) and `duration_seconds`.
4. On `IngestionCooldownError` → record `skipped` (not a failure).
5. On any other exception → record `failure` with the error message; **swallow
   it** so one failing job never crashes the scheduler or the app. Log at error
   level with the job name.

`run-now` reuses this exact wrapper so manual and scheduled runs are identical.

## Config (config.py + .env.example)

- `scheduler_enabled: bool = False` — master switch. Default **off** so
  `uv run app --reload` does not double-fire in dev. Set `true` via env in the
  docker-compose `app` service.
- `scheduler_run_retention_days: int = 30` — prune `JobRun` rows older than this.
  Pruning happens inline in `JobRunRepository.record()` (a single bounded
  `DELETE` of rows older than the cutoff after each insert) — no separate
  maintenance job.
- Cadence reuses the existing four settings — **no new schedule strings.**

`.env.example` gets `SCHEDULER_ENABLED` (with a comment that exactly one process
should set it true) and `SCHEDULER_RUN_RETENTION_DAYS`.

## docker-compose

Add `SCHEDULER_ENABLED: "true"` to the `app` service `environment` block so the
containerized deployment self-drives out of the box. Local `uv run app` stays
off unless the developer opts in.

## Frontend

Minimal admin **Scheduler** page under `pages/admin/`, matching existing admin
style and signals conventions:
- Table: job name, cron, enabled toggle, last-run status badge + timestamp,
  next-run time.
- "Run now" button per row.
- A per-domain `SchedulerService` wrapping the four HTTP calls; models in a
  `.model.ts` file.

## Migration & registry

- New Alembic migration creating `scheduler_job_runs` and `scheduler_job_toggles`.
- `JobRunOrm` and `JobToggleOrm` imported in `infrastructure/registry.py`.
- Post-merge reminder: run `uv run python -m alembic upgrade head` on the dev DB
  (CI runs on SQLite, so merged migrations don't auto-upgrade the running dev DB).

## Error handling

- Per-job isolation via the wrapper (above).
- Scheduler **startup** failure is caught and logged — the app still serves
  requests without the scheduler rather than failing to boot.
- `max_instances=1` + `coalesce=True` prevent overlapping/stacked runs.
- Status endpoints degrade gracefully when the scheduler is disabled (jobs list
  shows `enabled`/cadence with `next_run_at = null`).

## Testing

- **Unit:** wrapper records `success` / `failure` / `skipped` correctly; disabled
  toggle skips execution; `IngestionCooldownError` → `skipped`; retention prune
  drops only old rows.
- **Integration:** scheduler builds with fake domain services; `GET
  /scheduler/jobs` lists all four; `toggle` persists across reads; `run-now`
  invokes the underlying callable. Uses the in-memory SQLite + `StaticPool` +
  `require_auth` override conventions already in the suite.
- Tests invoke the registered job functions **directly** — no real APScheduler
  timing, no `sleep`. The runner's trigger wiring is validated separately by
  asserting the trigger objects built from config, not by waiting on the clock.

## Known limitation (documented, not solved)

`scheduler_enabled` must be true on **exactly one** process. With horizontal
replicas this would double-fire. Acceptable for the current single-user
deployment; multi-replica leader election is deferred.

## What this unblocks

- **Phase 2** (notifications) reads `JobRun` history + the autohunt `Digest`.
- **Phase 4** (autopilot pipeline) composes these independent jobs into a chain.

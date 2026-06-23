# Autopilot Pipeline — Design (Autopilot Phase 4)

**Date:** 2026-06-22
**Initiative:** [HireSense Autopilot](./2026-06-21-autopilot-initiative.md) — Phase 4
**Status:** Approved for planning
**Composes:** Phase 1 (scheduler), Phase 2 (notifications), Phase 3 (the review-queue pattern). Reuses the existing `applications` generation services.

## Goal

On a cadence, turn the autohunt digest's top new matches into ready-to-review
**application drafts** (application + match + tailored CV optimization + cover
letter), then notify the candidate. Sending/applying stays manual (Phase 5).
Auto-drafting is LLM-heavy, so it is opt-in and capped.

## Guiding decisions

1. **Orchestration, not new generation.** The `applications` module already
   exposes every step: `ApplicationService.create_from_ingested(job_id)`,
   `ArtifactService.generate_match(application_id, cv_language=...)`,
   `ArtifactService.generate_optimization(application_id, cv_language=..., match_id=...)`,
   `ApplyService.generate_cover_letter(application_id, cv_language=..., tone=...)`.
   Phase 4 calls these in sequence; it does not reimplement generation.
2. **Dedup/state in a new table — no applications-schema change.** An
   `autopilot_drafts` table keyed by `job_id` records the created
   `application_id`, per-job status, and batch timestamp. Re-runs skip jobs
   already drafted. This table also backs the review list and observability.
3. **Drafts are normal applications.** Each drafted job becomes a standard
   application in `saved` status with its artifacts pre-generated — reviewable in
   the existing applications UI. No status auto-advances; nothing is sent.
4. **Opt-in + capped.** `autopilot_pipeline_enabled` defaults **off**;
   `autopilot_pipeline_top_n` defaults **3**. This bounds LLM spend.

## Non-goals

- Outreach message drafting (belongs with Phase 5's outbound/send layer).
- Auto-apply / auto-send / auto-advancing application status (Phase 5).
- Interview-prep generation (premature before an interview signal).
- Changing the `applications` module schema or its generation services.
- Re-ranking or re-scoring — the pipeline consumes the autohunt digest's existing
  top-N taste-ranked entries as its input.

## Architecture — new `autopilot/` module (hexagonal)

> Distinct from the existing `autohunt` module (which produces digests). The
> `autopilot` module consumes a digest and drives drafting.

### `domain/`
- `draft_status.py` — `DraftStatus` enum: `drafted` | `partial` | `failed`
  (a job that created an application but whose later artifacts failed →
  `partial`; one that couldn't even create → `failed`; full success → `drafted`).
- `autopilot_draft.py` — `AutopilotDraft` (pure): `id`, `job_id: str`,
  `application_id: UUID | None`, `job_title: str | None`, `company: str | None`,
  `status: DraftStatus`, `detail: str | None`, `created_at`.
- `pipeline_result.py` — `PipelineResult` (pure): `created: int`,
  `skipped: int`, `drafts: list[AutopilotDraft]`.
- `ports/draft_repository.py` — `DraftRepository` Protocol: `add(draft)`,
  `list(limit)`, `exists_for_job(job_id) -> bool`.
- `ports/application_drafter.py` — `ApplicationDrafter` Protocol, the single
  seam over the `applications` services the pipeline needs:
  `async draft(job_id: str) -> tuple[UUID, DraftStatus, str | None]` (creates the
  application + generates match → optimization → cover letter; returns the new
  application id, the resulting status, and a detail/error string). Keeping this
  one port means the pipeline service depends on an interface, and the concrete
  adapter (in bootstrap/infra) wires the real `ApplicationService`/`ArtifactService`/
  `ApplyService`.
- `autopilot_pipeline_service.py` — `AutopilotPipelineService`:
  `async run() -> PipelineResult`. Reads the latest digest via an injected
  `latest_digest()` callable; iterates its top-N entries (already ordered);
  skips entries where `repo.exists_for_job(job_id)`; for each remaining, calls
  `drafter.draft(job_id)` (best-effort — a raised exception is caught, recorded as
  a `failed` `AutopilotDraft`, batch continues); records an `AutopilotDraft` per
  processed job; notifies (`notifier.notify_pipeline_drafts(created)`) when
  `created > 0`, best-effort. `run()` NEVER raises into the caller. `top_n` and
  the digest source are injected.

### `infrastructure/`
- `autopilot_draft_orm.py` — `AutopilotDraftOrm` (table `autopilot_drafts`,
  index on `job_id`). Registered in `infrastructure/registry.py`.
- `draft_repository.py` — `DraftRepositoryImpl(session_factory)` (extends
  `SqlRepository`).

### `api/`
- `provider.py`, `dependencies.py`, `routes.py` (auth-gated):
  - `GET /autopilot/drafts?limit=` — the recent drafts review list
    (`list[AutopilotDraft]`), each linking to its `application_id`.
  - `POST /autopilot/run` *(admin)* — trigger a run now (returns `PipelineResult`);
    useful for testing and manual kickoff.

## ApplicationDrafter adapter (bootstrap/infra seam)

A concrete `ServicesApplicationDrafter` (in `autopilot/infrastructure/` or
`bootstrap`) implements `ApplicationDrafter.draft(job_id)`:
1. `agg = await application_service.create_from_ingested(job_id)` →
   `application_id = agg.id`.
2. `match = await artifact_service.generate_match(application_id, cv_language=default)`.
3. `await artifact_service.generate_optimization(application_id, cv_language=default, match_id=match.id)`.
4. `await apply_service.generate_cover_letter(application_id, cv_language=default, tone=default)`.
Steps 2–4 are each wrapped so a later-step failure yields `DraftStatus.partial`
(the application + whatever generated is kept). A step-1 failure → `failed`
(no application). `cv_language`/`tone` come from existing config defaults.
The adapter returns `(application_id, status, detail)`.

## Configuration (config.py + .env.example)

- `autopilot_pipeline_enabled: bool = False` — gates the scheduler job entirely.
- `autopilot_pipeline_top_n: int = 3` — max digest entries drafted per run.
- `autopilot_pipeline_schedule: str = "0 10 * * *"` — cron for the `autopilot_pipeline`
  scheduler job (after the autohunt `0 9 * * *` cadence so a fresh digest exists).

## Scheduler integration (Phase 1)

`build_scheduler` gains an optional `autopilot_pipeline_service` param (default
`None`). When provided, it registers a 6th job `autopilot_pipeline` (cron
`autopilot_pipeline_schedule`) whose callable runs the service and returns
`result.created` (`count_items=int`). When `None` (default), the job is absent
and Phases 1–3 behavior is byte-identical. **Additionally**, the job is only wired
when `autopilot_pipeline_enabled` is true — `build_autopilot` returns `None` when
disabled, so `main.py` passes `None` and the job isn't registered (belt-and-braces
with the master `scheduler_enabled`).

## Notifications integration (Phase 2)

`NotificationService` gains `async notify_pipeline_drafts(count: int) -> bool`
(+ a `render_pipeline_drafts_email`), mirroring the existing best-effort methods.
The pipeline service calls it when a run produces ≥1 draft. Injected optionally.

## Error handling

- Per-job drafting is isolated: a raised exception → recorded `failed` draft, batch
  continues. A partial generation → `partial` draft (application kept).
- LLM-unconfigured (`generate_cover_letter` raises `RuntimeError`/503-equivalent)
  → that job is `partial` (match/optimization may have succeeded) or `failed`,
  recorded, never crashes the run.
- `run()` returns a `PipelineResult` even on a fully empty/failed batch; it never
  raises into the scheduler. Notification failure is swallowed.
- Dedup by `job_id` prevents re-drafting on subsequent runs.

## Frontend

An **Autopilot drafts** review surface (a page + nav entry, mirroring prior
phases): lists recent `AutopilotDraft`s (job title · company · status badge) with
a link to each created application (the existing application detail view is the
review/approve surface). A per-domain `AutopilotService` wraps `GET
/autopilot/drafts` (and optionally `POST /autopilot/run`); models in a `.model.ts`.
Standalone + signals + OnPush.

## Migration & registry

New Alembic migration `035_add_autopilot_drafts` (hand-written, numeric,
`down_revision="034"`) creating `autopilot_drafts` with an index on `job_id`.
`AutopilotDraftOrm` imported in `infrastructure/registry.py`. Post-merge:
`uv run python -m alembic upgrade head`.

## Testing

- **Unit:** `AutopilotPipelineService.run()` with a fake digest source + fake
  `DraftRepository` + fake `ApplicationDrafter`: drafts top-N; skips jobs already
  drafted (dedup); a drafter exception → `failed` draft, batch continues; notifies
  only when `created > 0`; respects `top_n`; never raises. `DraftStatus` mapping.
- **Integration:** `DraftRepositoryImpl` against SQLite (add/list/exists_for_job);
  `GET /autopilot/drafts` returns the list; `POST /autopilot/run` (admin) triggers
  a run with a fake drafter and returns a `PipelineResult`. Scheduler:
  `autopilot_pipeline` job present only when the service is injected; runs via
  fakes. `render_pipeline_drafts_email` includes the count. The `ServicesApplicationDrafter`
  adapter is tested with fake application/artifact/apply services asserting the
  call sequence and the partial/failed status mapping. No real LLM in tests.

## Decomposition fallback

The pipeline service + drafts store + status API + the drafter adapter form the
testable core (all fakeable). The scheduler job + notification method + frontend
are the thin automation/UX layer on top — land the core first if the plan runs long.

## What this unblocks

- Phase 5 (outbound) adds the gated "send/apply" actions on top of these drafts,
  plus outreach drafting and follow-up sequences.

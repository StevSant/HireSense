# Proactive Auto-Hunt — Design

**Date:** 2026-05-31
**Status:** Design proposed — supersedes the concept stub [2026-05-31-proactive-auto-hunt-concept.md](2026-05-31-proactive-auto-hunt-concept.md). Brainstormed and approved; pending its own implementation plan.
**Depends on:** ingestion (corpus + `SemanticPreRanker`), preference (taste vector via `query_vector`, already wired into the pre-ranker), profile (candidate skills/summary), and the existing external-cron trigger pattern (`POST /ingestion/revalidate`). The system is single-user and never self-schedules.

## Problem

HireSense is **pull**: the user opens the app and searches. Everything needed to flip it to **push** already exists — ingestion (with freshness via `fetched_at`), taste-ranked matching (`SemanticPreRanker` + the preference taste vector), and the profile. What's missing is an orchestrator that periodically surfaces the top *new* matches as a digest the user can glance at ("5 strong new roles since yesterday").

## Goals

1. A scheduled run computes the top-N **new** (since the last run) taste-ranked matches above a quality floor and persists a **digest**.
2. The app reads digests via GET endpoints (in-app surface; a frontend view is a later phase).
3. Reuse the **exact** ranking the jobs list uses, so "strong match" means the same thing everywhere.
4. No new outbound infrastructure; no self-scheduling; single-user.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | **Digest only.** Pre-drafting applications (CV/cover-letter into SAVED apps) is a clean follow-up spec, explicitly out of scope here. |
| Selection | **Top-N above a quality floor.** Taste-rank the new-since set, keep `score ≥ autohunt_min_score`, take top `autohunt_top_n`. A quiet day yields fewer/zero entries — never weak filler. |
| Delivery | **In-app only.** Persist digests; GET endpoints serve them. No email/push (would add outbound infra/secrets/deliverability). |
| "New since" | **Watermark = the latest digest's `created_at`.** Each newly-ingested job (immutable `fetched_at`) falls in exactly one run window → appears in at most one digest. No per-job "seen" table. |
| Trigger | **External cron `POST /autohunt/run`**, gated by the same `require_auth` as the rest of the API (cron uses a token), mirroring `POST /ingestion/revalidate`. The app never self-schedules. |
| Code location | New read+orchestrate **`autohunt` bounded context** that consumes ingestion/preference/profile; mirrors how `analytics` landed. |

## Architecture

### 1. Data model (`autohunt` context)

New table **`digests`** (one row per run — also a run log):

| column | type | notes |
|---|---|---|
| `id` | UUID PK | |
| `created_at` | timestamptz, default now() | run timestamp **and** the watermark for the next run |
| `cutoff_at` | timestamptz | the "new since" lower bound this run used |
| `entries` | JSON | denormalized snapshot `[{job_id, title, company, url, score}]` (may be empty) |
| `job_count` | int | `len(entries)` — convenience for list/badge |

- **Every run persists a row**, even when empty (`entries: []`, `job_count: 0`) — makes the watermark trivial (`next cutoff = latest.created_at`) and serves as a run log.
- **First run:** no prior digest → `cutoff_at = now() − autohunt_initial_lookback_days` (default 7), so it doesn't dump the backlog.
- **Denormalized entries** keep a digest stable/readable after jobs later close; read endpoints never re-rank or re-join.
- **No "seen" table** — the watermark guarantees one-digest-per-new-job.

Domain: `DigestEntry{ job_id: str, title: str, company: str, url: str | None, score: float }`; `Digest{ id, created_at, cutoff_at, entries: list[DigestEntry], job_count }` (one class per file). Repository port + impl (preference-pattern): `add(digest) -> Digest`, `latest() -> Digest | None`, `list_recent(limit: int) -> list[Digest]`, `prune_older_than(cutoff) -> int`. Alembic migration `018`.

### 2. The run orchestrator

`AutoHuntService.run() -> Digest` — pure orchestration over injected ports:

```
cutoff = (digest_repo.latest().created_at) or (now − initial_lookback_days)
new_jobs = jobs_repo.list_since(cutoff, bucket="boards", status="open")
view = profile_service.get_for_language(default_language)
if view is None:
    return digest_repo.add(Digest(cutoff_at=cutoff, entries=[], job_count=0))
candidate_skills, candidate_summary = flatten(view)            # skills + summary blob
skill_by_id = {}                                               # optional skill-overlap precompute (may be empty)
ranked = await pre_ranker.rerank(new_jobs, skill_by_id, candidate_skills, candidate_summary, "boards")
qualified = [j for j in ranked if (j.match_score is not None and j.match_score >= autohunt_min_score)][:autohunt_top_n]
entries = [DigestEntry(job_id=j.id, title=j.title, company=j.company, url=j.url, score=j.match_score) for j in qualified]
digest = digest_repo.add(Digest(cutoff_at=cutoff, entries=entries, job_count=len(entries)))
digest_repo.prune_older_than(now − autohunt_digest_retention_days)
return digest
```

**Injected ports (all existing except `list_since`):**
- `jobs_repo` — gains `list_since(cutoff, *, bucket, status="open") -> list[NormalizedJob]` (uses the existing `ix_ingested_jobs_bucket_fetched_at` index; filters `fetched_at >= cutoff`).
- `pre_ranker` (`SemanticPreRanker`, the **same instance** ingestion builds) — already applies `preference.query_vector`, so the digest is taste-ranked with no extra logic; falls back to passthrough if the vector store/embedding is unavailable.
- `profile_service.get_for_language` — candidate skills + summary (the same flatten the jobs endpoint uses).
- `digest_repo` — persistence + retention.

Pure orchestration over ports → unit-testable with fakes, no DB/model needed.

### 3. API, trigger & wiring

`autohunt/api/` (provider/dependencies/routes/`__init__`, mirroring preference/analytics), all auth-required:
- `POST /autohunt/run` → `AutoHuntService.run()`, returns the created digest summary. The external cron (the one already hitting `/ingestion/revalidate`) calls this; natural cron order: ingestion → revalidate → autohunt.
- `GET /autohunt/digests?limit=N` → recent digests.
- `GET /autohunt/digests/latest` → the most recent digest, or a neutral empty-state shape when none exist.

Bootstrap `build_autohunt(infra, jobs_repo, pre_ranker, profile_service)` in `main.create_app()` **after ingestion and profile**, receiving ingestion's existing jobs repo + pre-ranker (so the taste-aware pre-ranker instance is shared, not rebuilt). This requires `IngestionBuild` to additively **expose its jobs repo + pre-ranker** (small change, like Phase-2 exposing `status_history_read` on `TrackingBuild`). `app.state.autohunt = build.provider`; include the router.

**Settings** (config + `.env.example`): `autohunt_top_n=5`, `autohunt_min_score` (quality floor), `autohunt_initial_lookback_days=7`, `autohunt_digest_retention_days=90`, `autohunt_schedule` (informational only — documents intended cadence; never read to self-schedule). Confirm the default value for `autohunt_min_score` against the jobs list's `match_score` scale during planning (a 0–1 score; floor likely ~0.6).

## Error handling & edge cases

- **No profile** → empty digest, watermark advances, never errors.
- **No new jobs** / **none above floor** → empty digest (honest "nothing strong new").
- **Pre-ranker degraded** (no vector store / embedding fails → passthrough): `match_score` may be None/heuristic; the floor treats `None` / sub-threshold as **not qualifying**, so unranked filler is never surfaced as "strong"; log it; the run still persists a (likely empty) digest.
- **First run** → bounded `initial_lookback_days` window, not the whole corpus.
- **Duplicate cron fire** → two adjacent digests with overlapping windows at worst (a job in two same-day digests). Acceptable for a single-user daily cron; not locked.
- **Retention** → `prune_older_than` at the end of `run()` keeps the table bounded (no separate cron).
- **Auth** → `/autohunt/run` requires auth (cron token), same as revalidate.

## Testing

- **Unit (`AutoHuntService.run`, fakes for every port):** cutoff = latest digest's `created_at` else initial-lookback; floor filters sub-threshold and `None` scores; top-N cap; entries denormalized; empty-profile → empty digest + watermark advances; no-new-jobs → empty digest.
- **Repo (DB-backed SQLite):** `jobs_repo.list_since(cutoff)` returns only open jobs with `fetched_at >= cutoff`; `DigestRepository.add/latest/list_recent/prune_older_than` round-trip against the `018` ORM.
- **Integration (in-process FastAPI, auth overridden, real SQLite + fake pre-ranker/profile):** `POST /autohunt/run` builds a digest from seeded new jobs above the floor; a second run with no newer jobs yields an empty digest whose `cutoff_at == ` the first run's `created_at` (watermark chains); `GET /autohunt/digests/latest` returns it; `GET /autohunt/digests` lists recent.

## Out of scope (future, own specs)

Pre-drafted applications (CV/cover-letter into SAVED apps awaiting approval); email/push delivery; the frontend digest view/badge; portals-bucket inclusion; company-diversity capping; multi-user.

## Implementation sequencing note

Single cohesive plan, but the natural order is: (1) `digests` table + domain/repo + migration `018`; (2) `jobs_repo.list_since` + `IngestionBuild` exposing repo/pre-ranker; (3) `AutoHuntService` + unit tests; (4) API + bootstrap wiring + integration tests. Each step is independently testable.

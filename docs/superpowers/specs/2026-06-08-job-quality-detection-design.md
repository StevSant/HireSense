# Job Quality / Trash-&-Spam Detection — Design

**Date:** 2026-06-08
**Status:** Approved (direct user request — "do the full change correctly")
**Scope:** Detect and hide low-quality / fake / spam job listings (MLM pitches,
commission-only "be your own boss" roles, content-farm reposts, empty shells)
so they don't pollute the ingestion list. Triggered by listings like
"Marketing Automation SaaS + Services — Line of Business Owner" surfacing as
real jobs.

## Problem

The ingestion pipeline ranks and shows everything it fetches. Three classes of
junk slip through:

1. **Stale** — re-surfaced postings with an old `posted_date`. *(Handled
   separately by the `max_age_days` filter — out of scope here.)*
2. **Empty / data-quality** — blank company, no description. *(Partly handled
   by source-specific normalizer fixes, e.g. getonboard company resolution.)*
3. **Spam / scam / low-value** — MLM, franchise/"line of business owner",
   commission-only, pyramid pitches, recruiter content-farms. **This is what
   this feature targets.**

These are not reliably separable by keywords alone (a legit "Business
Development" role vs an MLM "be your own boss" pitch share vocabulary), so the
detector must be **LLM-backed**, not purely heuristic.

## Approach: classify once at ingestion, persist on the job, filter at query

Job quality is **intrinsic to the job and profile-independent**, so — unlike the
match score — it is computed **once when a job is ingested** (insert / update /
reopen) and persisted on the job row. The listing query then hides flagged jobs
by default, with an opt-in toggle to reveal them (mirrors the existing
`include_closed` / "Show closed" pattern).

### Hybrid classifier (deterministic fast-path + LLM)

`JobQualityClassifier` (ingestion domain service, depends only on `LLMPort`):

1. **Deterministic spam signals** (cheap, run first): a small set of
   high-precision markers — "line of business owner", "be your own boss",
   "commission only", "unlimited earning potential", MLM/franchise phrases,
   empty company **and** thin description, etc. A strong hit short-circuits to
   `SPAM` with the matched reason (no LLM call needed).
2. **LLM adjudication** (the non-heuristic part): for everything else, a single
   cheap-model call classifies the job as `ok | low_quality | spam` with a short
   reason. Batched per ingestion run, degrades to `OK` (fail-open — never hide a
   job because the LLM was unavailable) on error / no LLM configured.

Result: `JobQualityVerdict { quality: JobQuality, reason: str | None }`.

`JobQuality` ∈ `{ ok, low_quality, spam }`.

### Persistence

- `NormalizedJob` gains `quality: str = "ok"` and `quality_reason: str | None`.
- `JobOrm` gains `quality` + `quality_reason` columns (Alembic migration; the
  default backfills existing rows to `ok` so nothing is hidden retroactively).
- Repository maps both directions; content-hash is **not** affected by quality
  (quality is derived, not source data).

### Where it runs

In `IngestionOrchestrator.run`, after upsert, the same `touched` set that is
sent to the indexer is sent to the classifier; verdicts are persisted via a
batched score-style write. Classification failures are logged and skipped (the
job stays `ok`). This keeps it off the request path entirely.

### Query / API

- `filter_and_paginate` gains `include_low_quality: bool`. When `False`
  (default), jobs with `quality != "ok"` are hidden. Pgvector semantic search
  also excludes them (same as closed).
- `GET /ingestion/jobs` gains `include_low_quality` query param; the frontend
  adds a "Show low-quality" toggle next to "Show closed", and the detail panel
  shows the quality reason when flagged.

## Fail-open principle

Every uncertain path defaults to **showing** the job (`ok`): no LLM, LLM error,
parse failure, or unknown verdict → `ok`. Hiding a real job is worse than
showing a borderline one; the toggle always reveals everything.

## Testing

- Deterministic signals: spam phrases → `SPAM` without an LLM call.
- LLM path: stubbed LLM returns each verdict; fail-open on error / no LLM.
- Filter: `quality != ok` hidden unless `include_low_quality`.
- Orchestrator: touched jobs get classified + persisted; failure leaves `ok`.
- Migration: column added with `ok` default; round-trips through the repo.

## Non-goals

- Ghost-job / "is this company actually hiring" detection (needs external
  signals).
- Per-profile relevance (that's the match score, already handled).
- Re-classifying the entire existing corpus automatically — a one-off backfill
  endpoint can be added later; new/updated jobs are classified going forward.

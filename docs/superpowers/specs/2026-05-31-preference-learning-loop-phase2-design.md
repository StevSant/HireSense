# Preference Learning Loop — Phase 2

**Date:** 2026-05-31
**Status:** Design — decisions carried from the approved [Phase 1 spec](2026-05-31-preference-learning-loop-design.md); pending its own implementation plan
**Depends on:** Phase 1 (merged) — the `preference` bounded context, `FeedbackSignal`/`PreferenceModel`, `TasteVectorCalculator`, `PreferenceService`, and the `SemanticPreRanker` integration

## Problem

Phase 1 learns taste from **explicit** feedback only (thumbs / not-interested / more-like-this) and re-ranks via the taste vector. Two pieces from the original design were deliberately deferred:

- **Implicit outcomes are still discarded.** Every `TrackedApplication` transitions through
  `SAVED → APPLIED → INTERVIEWING → OFFERED → ACCEPTED / REJECTED`, but nothing feeds those
  outcomes back into the loop. The strongest ground-truth signal the system has (you got an
  interview / an offer / a rejection) never sharpens ranking.
- **Scoring weights never adapt.** The composite is a fixed weighted average of dimension
  scorers (comp, culture, growth, seniority, application-strength, interview-readiness). The
  loop can change *what surfaces* (taste vector) but not *how the surfaced set is scored*.

## Goals

1. **Implicit signal capture** — a tracking status transition auto-emits a `FeedbackSignal`
   so outcomes feed the taste vector alongside explicit feedback.
2. **Dimension-weight nudging** — learn which dimensions actually predicted positive outcomes
   and nudge their weights, conservatively and reversibly, gated on a minimum outcome count.
3. **Explanation v2** — an LLM-phrased drift summary layered over the Phase 1 deterministic
   counts ("leaning toward remote-first backend, away from large-enterprise").
4. **Preserve Phase 1 safety** — cold-start unchanged, fully reversible, decay still applies,
   no behavior change until enough outcome data exists.

## Decisions (carried from the original brainstorm)

| Decision | Choice |
|---|---|
| Implicit signal kinds | `applied`, `interviewing`, `offered`, `accepted`, `rejected` (already defined on `FeedbackKind`'s `_NEGATIVE` set / weight-key scheme; only `rejected` is negative) |
| Signal weights | tiered, config-driven: `offered`/`accepted` ≫ `thumbs_up`; `rejected` drives the negative term. Add the implicit per-kind weight settings deferred in Phase 1 |
| Transport | a new `tracking` domain event on the existing in-memory event bus; `preference` subscribes — no direct tracking→preference call |
| Weight nudging | correlation-based, **clamped** delta per dimension, **gated** on a minimum outcome count; stored as `weight_overrides` on the model; user-viewable and overridable |
| Decay consolidation | a nightly batch (external cron, like revalidation) recomputes the delta so it decays without new signals |
| Explanation v2 | LLM phrasing via the existing tracked-LLM factory, over the deterministic Phase 1 summary; falls back to the deterministic text on LLM failure |

## Architecture

### 1. Implicit signals (tracking → preference, event-driven)

- **New event** `kernel/events/tracking_status_changed.py`: `TrackingStatusChangedEvent(event_type="tracking.status_changed", job_id: str | None, status: str)`. Re-export from `kernel/events/__init__.py`.
- **Publish it**: `TrackingService` currently takes `(repository, ingestion_orchestrator)` and `update_status` just saves. Inject the event bus and publish `TrackingStatusChangedEvent` after a successful status change (skip when `job_id is None` — only ingestion-linked applications can map to an embedding). Wire the bus in `bootstrap/tracking.py`.
- **Subscribe in preference**: a thin subscriber (registered in `bootstrap/preference.py` after the service is built) maps the status to a `FeedbackKind` and calls a new
  `PreferenceService.record_implicit_signal(job_id, kind)` — identical to `record_signal` but with `source=IMPLICIT`. The existing `record_signal` already snapshots the embedding and recomputes; factor the shared body so both sources reuse it.
- **Settings** (deferred from Phase 1): `preference_weight_applied`, `preference_weight_interviewing`, `preference_weight_offered`, `preference_weight_accepted`, `preference_weight_rejected` (+ `.env.example`). `FeedbackKind.weight_key` already yields these names, so `build_preference`'s `{kind: getattr(s, kind.weight_key)}` dict picks them up once the enum members and settings exist.
- **Enum**: add the five implicit members to `FeedbackKind` (the `_NEGATIVE` set already lists `rejected`).

### 2. Dimension-weight nudging (preference → matching)

- **Learn**: a `WeightNudgeCalculator` (pure, unit-testable) takes, per dimension, the dimension's score on each outcome-bearing signal and the signal's polarity, and returns a **clamped** integer delta (e.g. ±3, hard absolute floor/ceiling) reflecting correlation with positive outcomes. Gated: returns all-zero until `>= N` outcome signals exist (cold-start guard).
- **Store**: `weight_overrides: dict[str, int]` on `PreferenceModel` (dimension name → delta), recomputed alongside the delta vector.
- **Apply**: matching's composite is a weighted average in `MatchingOrchestrator.evaluate`, where each `DimensionResult` carries its scorer's integer `weight` (wired from settings in `bootstrap/matching.py`). Inject an optional, duck-typed `preference` port into `MatchingOrchestrator`; in `evaluate`, look up `weight_overrides` and composite with `clamp(base_weight + delta)` instead of `base_weight`. No model / no overrides → identical to today (backward compatible, mirrors the Phase 1 pre-ranker pattern).
- **Expose**: `GET /preference/weights` returns base + override + effective per dimension; `weight_overrides` is included in `/explain`; `/reset` clears it.

### 3. Explanation v2 (LLM phrasing)

- Extend `PreferenceService.explain()` to optionally produce a natural-language summary: feed the deterministic counts + the nearest skill/company themes of positively- vs negatively-signaled jobs (titles fetched via the ingestion orchestrator by `job_id`) to the tracked LLM, returning one or two sentences. Deterministic Phase 1 fields remain; the LLM text is an additional `summary: str | None` field that is `None` on LLM failure or when disabled by a setting.

## Error handling & edge cases

- Status change with `job_id is None` → no event (cannot map to an embedding).
- Implicit signal for a not-yet-indexed job → same as Phase 1: stored, no contribution, logged.
- Weight nudging below the gate → all-zero overrides → scoring identical to today.
- LLM explanation failure → fall back to the deterministic summary; never block `/explain`.
- Duplicate transitions (e.g. re-saving the same status) → dedupe or accept idempotently (decide in planning; leaning: emit only on actual status change, which `update_status` can detect by comparing old vs new).

## Testing

- **Unit**: status→kind mapping; `record_implicit_signal` sets `source=IMPLICIT`; `WeightNudgeCalculator` clamping + cold-start gate + correlation direction; composite applies overrides and falls back when absent.
- **Integration**: a tracking `PATCH` status change emits the event and produces an implicit signal that shifts the taste vector; weight overrides change a composite score once the gate is met; `/reset` clears both delta and overrides.

## Out of scope (future)

Multi-profile preference models; per-source taste; A/B comparison of ranking with/without the loop.

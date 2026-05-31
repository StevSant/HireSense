# Preference Learning Loop

**Date:** 2026-05-31
**Status:** Design — approved, pending spec review
**Module scope:** new bounded context `preference`; integration touchpoints in `matching` and `tracking`

## Problem

HireSense scores every job *statically* against the candidate's profile. The
matching pipeline has two tunable surfaces — the global pgvector ANN
pre-ranking (against the CV/profile embedding) and the weighted-average
composite of dimension scorers — but neither ever changes based on what the
user actually does. The system already records rich outcome signals it throws
away:

- **Pipeline outcomes are discarded as a learning signal.** Every
  `TrackedApplication` carries a status trail
  (`SAVED → APPLIED → INTERVIEWING → OFFERED → ACCEPTED / REJECTED`) linked to a
  `job_id`. That is a labeled outcome for every job the user engaged — never fed
  back into ranking.
- **There is no way to express taste.** A user cannot tell the system "more like
  this" or "not interested." The only lever is editing the profile, which is
  coarse and indirect.
- **Ranking cannot track evolving preferences.** What the user wanted six months
  ago and today are weighted identically, forever.

The result: page 1 is frozen the moment the profile is set, and gets no better
the more the user uses the product.

## Goals

1. **Learn from both explicit and implicit signal** — immediate in-app feedback
   (thumbs / not-interested / more-like-this) *and* the existing pipeline
   outcome trail.
2. **Re-rank what surfaces** via a learned "taste vector" that drifts from the
   CV baseline toward positives and away from negatives.
3. **Nudge how the surfaced set scores** by adjusting dimension weights toward
   the dimensions that actually predicted positive outcomes (secondary, gated).
4. **Stay transparent and reversible** — the drift is explainable, signals
   decay, and the model resets to baseline on one click. The loop must never
   become an un-inspectable black box.
5. **Be cold-start safe** — zero signals must reproduce today's behavior
   exactly.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Learning signal | **Both** explicit + implicit, staged (explicit first to beat cold-start, implicit layered in) |
| Primary mechanism | **Taste vector** (Rocchio relevance feedback) re-ranking the pgvector ANN |
| Secondary mechanism | **Dimension-weight nudging**, conservative + gated on a minimum outcome count |
| Model type | **Rocchio centroid**, not a learned classifier (closed-form, stable at single-user data volumes) |
| Control model | **Transparent & reversible** — `explain` + `signals` audit + `reset`, with recency decay |
| Module | New bounded context `preference`; `matching` consumes it, `tracking` feeds it |
| Phasing | **Phase 1** taste vector + explicit feedback + transparency/reset (independently shippable). **Phase 2** implicit outcome signals + dimension-weight nudging |

## Approach choice: Rocchio over a learned classifier

Two viable ways to build the taste model:

- **Rocchio relevance feedback (chosen)** — the taste vector is a weighted
  centroid of the CV baseline pulled toward positively-signaled job embeddings
  and pushed away from negatives. Closed-form, no training step, stable from the
  very first label, recomputes in milliseconds as vector sums. Slots directly
  into the existing pgvector ANN.
- **Learned classifier** (e.g. logistic regression over dimension features) —
  needs dozens of labels to stabilize, adds retraining infrastructure, and
  overfits a single user's sparse data. Rejected; it is the right tool for
  many-user data, not one user.

## Architecture

A new bounded context `preference`, following the house layered shape
(`api → domain ← infrastructure`, ports as `Protocol`s). It owns three concerns:

1. **Feedback signals** — the input record.
2. **The preference model** — taste vector + weight overrides + provenance.
3. **The explanation / audit surface** — why the model is where it is, and reset.

`matching` becomes a *consumer*: at retrieval time it asks `preference` for a
query vector (the taste vector, or the CV embedding when no model exists) and
for dimension-weight overrides. `tracking` becomes a *producer*: a status
transition emits a domain event that `preference` subscribes to.

```
tracking ──(status-change event)──▶ preference ◀──(explicit feedback POST)── frontend
                                        │
                                        ├─ taste_vector  ─────▶ matching retrieval (pgvector ANN query)
                                        └─ weight_overrides ──▶ matching composite scoring
```

## Data model

- **`FeedbackSignal`**
  - `id`, `job_id`
  - `source`: `explicit` | `implicit`
  - `kind`: explicit → `thumbs_up`, `thumbs_down`, `not_interested`,
    `more_like_this`; implicit → `applied`, `interviewing`, `offered`,
    `accepted`, `rejected`
  - `polarity`: derived (+/−) from `kind`
  - `job_embedding`: **snapshot** of the job's embedding at signal time (pgvector
    column) — keeps recompute deterministic and decay-able even if the job is
    later pruned/closed
  - `created_at`
- **`PreferenceModel`** (one row per profile)
  - `taste_vector` (pgvector)
  - `baseline_vector` (= current CV/profile embedding)
  - `weight_overrides` (JSON: `dimension → bounded integer delta`)
  - `version`, `updated_at`

Both require an Alembic migration. `preference` owns its own ORM tables; it does
not reach into `tracking` or `matching` storage.

## The math (Rocchio + decay)

```
taste = normalize( α·baseline
                 + β·Σ (decayᵢ · wᵢ · job_vecᵢ)   over positive signals
                 − γ·Σ (decayⱼ · wⱼ · job_vecⱼ)   over negative signals )

decay = exp(−Δt / τ)            # Δt = age of the signal; stale signals fade
```

- **Signal weights `wᵢ` are tiered** and config-driven: a strong outcome
  (`offered`, `accepted`) outweighs a `thumbs_up`; `rejected` / `not_interested`
  drive the negative term. Tier values are a setting, not a literal.
- **All coefficients (`α, β, γ, τ`) and per-kind weights live in the settings
  layer** (`.env` + `.env.example` + config module) per the no-hardcoded-values
  rule — never inline literals.
- **Recompute** runs online on each new signal (cheap vector sum); a nightly
  batch consolidation re-applies decay so models drift even without new signals.
- The taste vector is **always normalized**, bounding its influence.

## Dimension-weight nudging (Phase 2, secondary)

For each dimension scorer, track the correlation between its score and positive
outcomes across accumulated signals. Nudge the dimension's integer weight by a
**clamped delta** (e.g. ±3 with hard absolute bounds). The whole mechanism is
**gated on a minimum outcome count** so a couple of clicks cannot swing scoring.
Result is persisted as `weight_overrides`, fully viewable and user-overridable
via the API. Default weights are unchanged until the gate is met.

## Integration with matching

- **Retrieval.** The pgvector ANN query vector becomes the `taste_vector` when a
  `PreferenceModel` exists for the profile; **it falls back to the raw CV /
  profile embedding when no model exists** — making today's behavior the exact
  zero-signal default. Fully backward-compatible.
- **Scoring.** The composite applies `weight_overrides` on top of each scorer's
  default integer weight (clamped). With no overrides, scoring is identical to
  today.

These are the only two changes inside `matching`; both are read-only lookups
against `preference` through a port.

## Capture surfaces

- **Explicit** — thumbs / "not interested" / "more like this" controls on match
  cards in the Angular frontend → `POST /preference/feedback`.
- **Implicit** — `tracking` publishes a new domain event on status transition
  (mirroring the existing `MatchCompletedEvent` event-bus pattern). `preference`
  subscribes and auto-emits a `FeedbackSignal` from the transition. *(Requires
  adding the status-change event to `tracking`; small, isolated addition.)*

## Transparency & control (API)

- `GET /preference/explain` — plain-language drift summary (e.g. "leaning toward
  remote-first backend roles, away from large-enterprise"). Derived by comparing
  the taste vector against the baseline over nearest skill / theme clusters;
  optionally phrased by the LLM through the existing provider abstraction.
- `GET /preference/signals` — the audit trail of contributing signals.
- `POST /preference/feedback` — record an explicit signal.
- `POST /preference/reset` — wipe the model back to the CV baseline. Recency
  decay handles staleness automatically between resets.

## Error handling & edge cases

- **No model / no signals** → CV-embedding fallback (cold-start safe; reproduces
  current behavior bit-for-bit).
- **Missing embedding snapshot** on a signal → skip its contribution, log a
  warning; never block recompute.
- **CV / profile change** → `baseline_vector` re-anchors and the taste vector
  recomputes; persisted feedback contributions survive and re-anchor onto the
  new baseline.
- **Bounds** → taste vector always normalized; weight nudges clamped to hard
  bounds; weight-learning gated on a minimum label count.

## Testing

- **Unit**
  - Rocchio recompute: positive signal pulls taste toward the job vector;
    negative pushes away; decay reduces an older signal's influence relative to a
    fresh one.
  - Weight-nudge: clamping holds at bounds; cold-start gate suppresses nudging
    below the minimum label count.
  - Fallback: no model → query vector equals the CV embedding; no overrides →
    composite equals today's.
- **Integration**
  - Explicit feedback → model update → retrieval query vector changes → observed
    ranking reflects it.
  - `tracking` status transition emits an implicit `FeedbackSignal`.
  - `POST /preference/reset` restores the baseline and ranking returns to
    cold-start order.

## Phasing

- **Phase 1 (independently shippable):** `preference` context, `FeedbackSignal`
  + `PreferenceModel` tables, Rocchio recompute with decay, explicit feedback
  endpoint + frontend controls, retrieval integration with CV fallback,
  `explain` / `signals` / `reset`. Delivers most of the value.
- **Phase 2:** `tracking` status-change event + implicit signal subscription,
  dimension-weight nudging (gated), weight-override application in composite
  scoring.

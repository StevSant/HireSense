# Preference Phase 2 — Dimension-Weight Nudging (Part 2) — Concept Stub

**Date:** 2026-05-31
**Status:** ⚠️ DEFERRED — split out of the [Phase 2 design](2026-05-31-preference-learning-loop-phase2-design.md). Parts 1 (implicit signals) + 3 (explanation v2) are planned in `docs/superpowers/plans/2026-05-31-preference-phase2-implicit-and-explanation.md`. This part is deferred because it requires architectural plumbing the original spec glossed over. Brainstorm/design before planning.

## Goal (unchanged from Phase 2 spec)

Learn which scoring dimensions actually predicted positive outcomes and nudge their weights — conservatively, clamped, reversible, gated on a minimum outcome count. Store as `weight_overrides: dict[str, int]` on `PreferenceModel`; apply in `MatchingOrchestrator.evaluate`'s composite as `clamp(base_weight + delta)`; expose via `GET /preference/weights`, include in `/explain`, clear on `/reset`.

## Why it was deferred — architectural blockers found during planning

1. **The 6 weighted `DimensionResult` scores are never persisted.** `MatchingOrchestrator.evaluate()` computes them on demand for `/matching/evaluate` and `/matching/batch-evaluate` and returns them to the client. `job_match_cache` stores only a Tier-1 `quick_score` + `quick_payload` (reasons/dealbreakers) and a Tier-2 `deep_payload` (`DeepAnalysisResult` with LLM-generated `DeepDimension` labels that don't map 1:1 to the six weighted scorers and only exist for jobs whose detail panel was opened). So the nudge calculator has **no data source** for "the dimension's score on each outcome-bearing signal."

2. **`evaluate()` has no `job_id`.** It receives a plain job dict (`{title, company, description, skills, location}`); the `/evaluate` route passes no id and batch passes `source_id` (the *tracked-app* id for tracked rows, only the real job id for ingested rows). Persisting per-dimension scores keyed by the feedback signal's `job_id` therefore requires **threading `job_id` through `evaluate()` and both call sites** — a matching API-contract change.

## Decided direction (from review, 2026-05-31)

- **Persist eval dimensions, then nudge.** Add a small store (likely in `SharedInfra`, built before both `build_preference` and `build_matching`) that upserts `{job_id: [DimensionResult...]}` whenever `evaluate()` runs. Weight-nudging reads from it; outcome jobs with no cached evaluation simply don't contribute (logged). Needs: a migration (new table + `weight_overrides` column on `preference_models`), `job_id` threading, an optional duck-typed write port on `MatchingOrchestrator`, and an optional read dependency + `WeightNudgeCalculator` (pure) on `PreferenceService`, plus an optional duck-typed `preference` read port on `MatchingOrchestrator` to apply the overrides in the composite (mirroring the `SemanticPreRanker` preference-port pattern).

## Open questions to resolve in brainstorming

1. **Store keying & single-user assumption.** Key by `job_id` alone (evaluate is called with `profile=None` today; system is effectively single-user), or by `(job_id, profile_hash)` like `job_match_cache`?
2. **Where the upsert happens.** Inside `evaluate()` via an injected optional store (covers both the route and batch since both go through `evaluate`), vs. at the call sites.
3. **Nudge math.** Correlation of each dimension's score with outcome polarity; clamp bound (±3?), absolute floor/ceiling, and the minimum-outcome gate (N). Recompute alongside the delta vector (and in the nightly decay batch).
4. **Cold-start / coverage.** Behavior when most outcome jobs have no cached dimensions (likely common early on) — the gate should keep overrides all-zero until enough covered outcomes exist.
5. **Exposure.** `GET /preference/weights` shape (base + override + effective per dimension); include `weight_overrides` in `/explain`; `/reset` clears it.

## Explicitly undecided

The data-model and nudge-math details above. Run `superpowers:brainstorming` to produce an approved design, then `writing-plans`.

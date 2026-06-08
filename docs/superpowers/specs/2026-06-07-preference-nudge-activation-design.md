# Preference Weight-Nudging — Activation (dimension-score source) — Design

**Issues:** #36 (activation) → closes epic **#34**. Builds on the merged nudging mechanism (PR #64).

## The blocker this resolves

`WeightNudgeCalculator` correlates each matching dimension's score on outcome-bearing jobs with the
outcome polarity to produce clamped weight deltas. The mechanism (calculator, `weight_overrides`
storage, `MatchingOrchestrator` application, `/preference/weights`) is merged but **inert**: there was
no source of per-job dimension scores. We evaluated the candidates:

- **Stored application match** (`ApplicationMatchOrm`) — only persists semantic/skill/experience/
  language, *not* the 6 LLM dimension scorers (compensation/culture/growth/seniority/
  application_strength/interview_readiness). Incomplete.
- **Deep-analysis cache** (`job_match_cache.deep_payload`) — has a full breakdown but only for jobs
  the user explicitly deep-analyzed. Too sparse.
- **Live recompute at override-compute time** (the current unattached seam) — would re-run LLM
  scorers every recompute and fails once the job is pruned.

## Decision (chosen): snapshot at outcome time onto the signal

When an **outcome** (implicit) signal is recorded — `applied` / `interviewing` / `offered` /
`accepted` / `rejected` — run the matching dimension scorers for that job × current profile **once**,
and store the resulting `{dimension: score}` map on the `FeedbackSignal`. Rationale:

- **Complete** — all configured dimensions, straight from the real scorers.
- **Ground-truth & durable** — captures the scores as they were at the outcome moment and survives
  later job pruning / embedding cleanup (the scores live on the signal, not the job).
- **Bounded cost** — outcomes are rare (you apply to / hear back on a small number of jobs), and the
  capture runs in the async event-bus subscriber, off the request path. LLM/profile/job unavailable →
  `None` → signal still stored, simply no nudging contribution (graceful, mirrors the embedding path).
- Explicit thumbs signals do **not** capture dimensions — nudging is outcome-driven only.

## Changes

### Domain
- `FeedbackSignal`: add `dimension_scores: dict[str, float] | None = None`.
- New port `preference/ports` `DimensionScorerPort` (Protocol): `async score_dimensions(job_id: str) -> dict[str, float] | None`.
- `PreferenceService._record(... , capture_dimensions: bool)`: for outcome (implicit) signals, when a
  dimension scorer is attached, `await scorer.score_dimensions(job_id)` and set it on the signal
  before persisting. `record_signal` (explicit) passes `capture_dimensions=False`;
  `record_implicit_signal` passes `True`.
- `_compute_overrides`: build `OutcomeObservation`s from each signal's **stored** `dimension_scores`
  (signals without them — explicit, or capture-failed — contribute nothing) + `signal.kind.polarity`.
  Remove the live `_dimension_lookup` / `attach_dimension_lookup` / `_dimension_scores_for` seam;
  replace with `attach_dimension_scorer(scorer)` used at record time.

### Infrastructure
- `FeedbackSignalOrm`: add `dimension_scores` JSON column; repository maps it ↔ domain. Migration `021`.

### Bootstrap (the cross-module wiring, allowed only here)
- A `DimensionScorerPort` adapter that, given `job_id`, fetches the job (ingestion orchestrator) +
  current profile (profile service) and runs the matching dimension scorers (collect
  `{result.dimension: result.score}`), returning `None` on any miss. Attached to the preference
  service post-build (matching is built after preference — same two-phase pattern as the existing
  `attach_job_lookup`).

## Backward compatibility
No scorer attached, scorer returns `None`, or the cold-start gate unmet → no signals carry dimension
scores → `weight_overrides` empty → `MatchingOrchestrator` composite **byte-identical** to today.

## Testing
- Unit: `_record` captures dimensions for implicit signals (scorer attached) and skips for explicit;
  `_compute_overrides` builds observations from stored `dimension_scores` and ignores signals without
  them; backward-compat (no scorer → empty).
- Integration: enough outcome events (status changes) → signals stored with dimension scores → gate
  met → `weight_overrides` populated → a matching composite changes; `/reset` clears delta + overrides;
  a capture failure degrades gracefully.

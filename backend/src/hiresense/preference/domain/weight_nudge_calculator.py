from __future__ import annotations

from collections import defaultdict

from hiresense.preference.domain.outcome_observation import OutcomeObservation


class WeightNudgeCalculator:
    """Pure, deterministic dimension-weight nudging (Phase 2 secondary loop).

    Per dimension, it correlates the dimension scorer's score against the
    outcome polarity across accumulated outcome-bearing signals and turns that
    correlation into a small **clamped integer** weight delta. The intent: if a
    dimension consistently scored *high* on jobs that led to positive outcomes
    (and low on negative ones), nudge that dimension's weight up; the reverse
    nudges it down.

    Two safety properties, both config-driven (no literals):

    - **Cold-start gate** — returns an empty override map until at least
      ``min_outcomes`` outcome observations exist, so a couple of clicks can
      never move scoring. Below the gate, callers see no overrides and matching
      is byte-identical to today.
    - **Hard clamp** — every delta is clamped to ``[-clamp, +clamp]`` so the
      mechanism can only ever bend weights, never dominate them.

    The correlation uses a sign-aligned mean: each dimension's score is centered
    at 0.5 (the neutral score) and multiplied by the signal polarity, then
    averaged. A positive mean means the dimension's score tracked positive
    outcomes; a negative mean means it tracked negative ones. The mean lies in
    [-0.5, 0.5]; ``scale`` maps it onto the integer delta range before clamping.
    """

    def __init__(self, *, min_outcomes: int, clamp: int, scale: float) -> None:
        self._min_outcomes = min_outcomes
        self._clamp = abs(clamp)
        self._scale = scale

    def compute_overrides(self, observations: list[OutcomeObservation]) -> dict[str, int]:
        # Cold-start gate: count distinct outcome signals. Observations are
        # per-(signal, dimension); a single signal contributes one observation
        # per dimension, so gate on the max per-dimension observation count
        # (== number of outcome signals when every signal scores every dim).
        if not observations:
            return {}
        by_dim: dict[str, list[OutcomeObservation]] = defaultdict(list)
        for obs in observations:
            by_dim[obs.dimension].append(obs)
        outcome_count = max(len(v) for v in by_dim.values())
        if outcome_count < self._min_outcomes:
            return {}

        overrides: dict[str, int] = {}
        for dimension, obs_list in by_dim.items():
            # Center each score at the neutral 0.5 and align with polarity, then
            # average. Positive => dimension high-scored positive outcomes.
            correlation = sum((o.dimension_score - 0.5) * o.polarity for o in obs_list) / len(
                obs_list
            )
            delta = round(correlation * self._scale)
            delta = max(-self._clamp, min(self._clamp, delta))
            if delta != 0:
                overrides[dimension] = delta
        return overrides

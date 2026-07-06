from __future__ import annotations

import math
from collections import Counter

from pydantic import BaseModel, Field

from hiresense.preference.domain.feedback_signal import FeedbackSignal


class PreferenceExplanation(BaseModel):
    active: bool
    total_signals: int
    positive_count: int
    negative_count: int
    counts_by_kind: dict[str, int]
    drift_magnitude: float
    # Phase 2: learned per-dimension weight deltas applied to matching scoring.
    weight_overrides: dict[str, int] = Field(default_factory=dict)
    summary: str | None = None


def build_explanation(
    signals: list[FeedbackSignal],
    *,
    delta_vector: list[float] | None,
    weight_overrides: dict[str, int] | None = None,
) -> PreferenceExplanation:
    counts = Counter(s.kind.value for s in signals)
    positive = sum(1 for s in signals if s.kind.polarity > 0)
    negative = sum(1 for s in signals if s.kind.polarity < 0)
    magnitude = math.sqrt(sum(x * x for x in delta_vector)) if delta_vector else 0.0
    return PreferenceExplanation(
        active=bool(delta_vector) and magnitude > 0.0,
        total_signals=len(signals),
        positive_count=positive,
        negative_count=negative,
        counts_by_kind=dict(counts),
        drift_magnitude=magnitude,
        weight_overrides=dict(weight_overrides or {}),
    )

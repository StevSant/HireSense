from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutcomeObservation:
    """One outcome-bearing signal's view of a single dimension.

    ``dimension_score`` is that dimension scorer's [0, 1] score for the job the
    signal was about; ``polarity`` is the signal's outcome polarity (+1 for a
    positive outcome such as an offer, -1 for a negative one such as a
    rejection). The :class:`WeightNudgeCalculator` correlates the two across all
    observations for a dimension to decide whether to nudge that dimension's
    weight.
    """

    dimension: str
    dimension_score: float
    polarity: int

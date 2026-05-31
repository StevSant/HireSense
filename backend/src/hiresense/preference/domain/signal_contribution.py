from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalContribution:
    """Resolved inputs for one signal's contribution to the delta vector."""

    embedding: list[float]
    polarity: int      # +1 or -1
    weight: float      # configured magnitude for the kind
    age_days: float    # signal age, for recency decay

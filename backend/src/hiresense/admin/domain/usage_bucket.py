from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UsageBucket:
    """One row of a grouped/aggregated usage query (timeseries or breakdown)."""

    key: str
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float

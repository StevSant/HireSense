from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UsageTotals:
    """Aggregate token/cost totals over a usage-log window."""

    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float

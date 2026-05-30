from __future__ import annotations

import enum


class QuickMatchVerdict(str, enum.Enum):
    """Coarse fit verdict for the quick (cheap-model) match score."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"

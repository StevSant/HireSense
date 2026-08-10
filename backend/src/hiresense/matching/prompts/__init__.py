"""Prompt text owned by the matching context.

Pure text plus f-string assembly — no ports, no IO — so `domain/` stays
importable from here without weakening its purity rules.
"""

from hiresense.matching.prompts.combined_scorer_prompt import render_combined_system_prompt
from hiresense.matching.prompts.deep_analysis_prompt import render_deep_analysis_system_prompt
from hiresense.matching.prompts.dimension_rubric import (
    ALL_DIMENSIONS,
    APPLICATION_STRENGTH,
    COMPENSATION,
    CULTURE_FIT,
    DIMENSION_NAMES,
    DimensionRubric,
    GROWTH_POTENTIAL,
    INTERVIEW_READINESS,
    SENIORITY_FIT,
)

__all__ = [
    "ALL_DIMENSIONS",
    "APPLICATION_STRENGTH",
    "COMPENSATION",
    "CULTURE_FIT",
    "DIMENSION_NAMES",
    "DimensionRubric",
    "GROWTH_POTENTIAL",
    "INTERVIEW_READINESS",
    "SENIORITY_FIT",
    "render_combined_system_prompt",
    "render_deep_analysis_system_prompt",
]

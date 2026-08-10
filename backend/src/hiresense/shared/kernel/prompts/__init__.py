"""Prompt policy that genuinely spans bounded contexts.

Deliberately narrow. Per-context prompt text belongs in that context's own
`<module>/prompts/` package — a repo-wide prompt dump would erase the context
boundaries. What lives here is policy two or more contexts must AGREE on, which
is the same reason `PromptBoundary` already sits in the kernel: the alternative
is an ingestion -> matching domain edge, exactly the kind this branch has been
removing.
"""

from hiresense.shared.kernel.prompts.fingerprint import prompt_fingerprint
from hiresense.shared.kernel.prompts.match_gating_rules import (
    BATCH_SCORING_CONSEQUENCES,
    DEEP_ANALYSIS_CONSEQUENCES,
    GatingConsequences,
    render_gating_rules,
)
from hiresense.shared.kernel.prompts.verdict_bands import (
    MODERATE_THRESHOLD,
    STRONG,
    STRONG_THRESHOLD,
    MODERATE,
    WEAK,
    verdict_label,
)

__all__ = [
    "BATCH_SCORING_CONSEQUENCES",
    "DEEP_ANALYSIS_CONSEQUENCES",
    "GatingConsequences",
    "MODERATE",
    "MODERATE_THRESHOLD",
    "STRONG",
    "STRONG_THRESHOLD",
    "WEAK",
    "prompt_fingerprint",
    "render_gating_rules",
    "verdict_label",
]

from __future__ import annotations

# Score bands shared by every candidate-vs-job fit verdict.
#
# These lived as private literals in BOTH quick_scoring_service.py and
# deep_analysis_service.py, alongside two copies of the same
# `_verdict_from_score` ladder. The prompts also restated the numbers in prose
# ("strong (>= 0.7)"), so three places had to be edited in lockstep to change a
# band and nothing enforced it. The prompt text is now rendered from these
# constants, so code and prose cannot disagree.
STRONG_THRESHOLD = 0.7
MODERATE_THRESHOLD = 0.4

STRONG = "strong"
MODERATE = "moderate"
WEAK = "weak"


def verdict_label(score: float) -> str:
    """Band a 0..1 fit score into strong / moderate / weak."""
    if score >= STRONG_THRESHOLD:
        return STRONG
    if score >= MODERATE_THRESHOLD:
        return MODERATE
    return WEAK

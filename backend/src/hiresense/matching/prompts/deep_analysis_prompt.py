from __future__ import annotations

from hiresense.shared.kernel.prompts import DEEP_ANALYSIS_CONSEQUENCES, render_gating_rules

# Deep analysis reports on its own five fields rather than the six scored
# dimensions — it is a narrative breakdown, not a second composite. Kept
# separate from matching.prompts.dimension_rubric for exactly that reason.
DEEP_DIMENSIONS: tuple[str, ...] = (
    "seniority_fit",
    "skills_role_fit",
    "growth",
    "culture",
    "compensation",
)


def render_deep_analysis_system_prompt() -> str:
    """System prompt for the single-job tier-2 analysis."""
    return (
        "You are an expert technical recruiter producing an honest, detailed match "
        "analysis between a CANDIDATE and ONE job. Return ONLY a JSON object:\n"
        "{\n"
        '  "overall_score": <0.0-1.0>,\n'
        '  "verdict": "strong|moderate|weak",\n'
        '  "dimensions": [{"dimension": "<name>", "score": <0-1>, "rationale": "..."}],\n'
        '  "matched_skills": ["..."], "missing_skills": ["..."],\n'
        '  "pros": ["..."], "cons": ["..."], "recommendations": ["..."],\n'
        '  "narrative": "2-4 sentence honest summary"\n'
        "}\n"
        f"Use exactly these dimension names: {', '.join(DEEP_DIMENSIONS)}.\n\n"
        f"{render_gating_rules(DEEP_ANALYSIS_CONSEQUENCES)}"
    )

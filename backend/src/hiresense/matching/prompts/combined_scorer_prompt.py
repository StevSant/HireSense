from __future__ import annotations

from hiresense.matching.prompts.dimension_rubric import ALL_DIMENSIONS, DIMENSION_NAMES


def render_combined_system_prompt() -> str:
    """System prompt for scoring all six dimensions in one call.

    Assembled from the same DimensionRubric objects the individual scorers
    render, so the two interchangeable paths cannot describe a dimension
    differently.
    """
    dimensions = "\n".join(rubric.inline() for rubric in ALL_DIMENSIONS)
    return (
        "You are a job-matching dimension scorer. Score a JOB against an optional "
        "CANDIDATE profile across ALL of the following dimensions in a single pass. "
        "For each, score 0.0 (terrible fit) to 1.0 (perfect fit) with a 1-2 sentence "
        "rationale.\n\n"
        f"{dimensions}\n\n"
        "Return ONLY a JSON object:\n"
        '{"dimensions": [{"dimension": "<name>", "score": <0.0-1.0>, "rationale": "<brief>"}]}\n'
        "Include exactly one entry per dimension, using exactly these names: "
        f"{', '.join(DIMENSION_NAMES)}."
    )

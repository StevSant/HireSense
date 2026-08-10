from __future__ import annotations

import pytest

from hiresense.ingestion.prompts import render_quick_scoring_system_prompt
from hiresense.shared.kernel.prompts import (
    BATCH_SCORING_CONSEQUENCES,
    DEEP_ANALYSIS_CONSEQUENCES,
    MODERATE_THRESHOLD,
    STRONG_THRESHOLD,
    render_gating_rules,
    verdict_label,
)
from hiresense.matching.domain.scorers import (
    ApplicationStrengthScorer,
    CompensationScorer,
    CultureScorer,
    GrowthScorer,
    InterviewReadinessScorer,
    SeniorityScorer,
)
from hiresense.matching.prompts import (
    ALL_DIMENSIONS,
    APPLICATION_STRENGTH,
    COMPENSATION,
    CULTURE_FIT,
    DIMENSION_NAMES,
    GROWTH_POTENTIAL,
    INTERVIEW_READINESS,
    SENIORITY_FIT,
    render_combined_system_prompt,
    render_deep_analysis_system_prompt,
)

# These prompts are not independent texts that happen to be similar — they are
# alternative renderings of one policy, and the system is only correct while
# they agree. Before the rubric was extracted they had already drifted (the
# combined prompt said culture_fit covered "collaboration style" while the
# individual scorer asked for "team-oriented vs. solo"; the deep-analysis
# gating rules omitted both the peripheral-tools carve-out and the discipline
# list that the quick prompt spelled out). Nothing failed when that happened.

_JOB = {
    "title": "Senior Go Engineer",
    "company": "Acme",
    "description": "Build distributed systems.",
    "location": "Remote",
    "salary_range": "$100k",
    "skills": ["go", "kubernetes"],
}

_SCORER_FOR_RUBRIC = [
    (SeniorityScorer, SENIORITY_FIT),
    (CompensationScorer, COMPENSATION),
    (GrowthScorer, GROWTH_POTENTIAL),
    (CultureScorer, CULTURE_FIT),
    (ApplicationStrengthScorer, APPLICATION_STRENGTH),
    (InterviewReadinessScorer, INTERVIEW_READINESS),
]


@pytest.mark.parametrize(
    ("scorer_cls", "rubric"), _SCORER_FOR_RUBRIC, ids=[r.name for _, r in _SCORER_FOR_RUBRIC]
)
def test_combined_and_individual_paths_state_identical_criteria(scorer_cls, rubric) -> None:
    """The two scoring paths are drop-in replacements, so they must describe
    each dimension identically. Every criterion must appear in both."""
    combined = render_combined_system_prompt()
    individual = scorer_cls(llm=None, weight=10, job_char_limit=500)._build_prompt(_JOB, None)

    for criterion in rubric.criteria:
        assert criterion in combined, f"{rubric.name}: {criterion!r} missing from combined prompt"
        assert criterion in individual, f"{rubric.name}: {criterion!r} missing from its scorer"


def test_combined_prompt_names_every_dimension() -> None:
    combined = render_combined_system_prompt()
    assert DIMENSION_NAMES == tuple(d.name for d in ALL_DIMENSIONS)
    for name in DIMENSION_NAMES:
        assert name in combined


@pytest.mark.parametrize("consequences", [BATCH_SCORING_CONSEQUENCES, DEEP_ANALYSIS_CONSEQUENCES])
def test_both_tiers_share_the_same_gating_criteria(consequences) -> None:
    """Batch scoring and deep analysis may differ in what they DO when a gate
    trips, but not in what trips it."""
    rendered = render_gating_rules(consequences)

    # The specific carve-outs that stop keyword overlap from inflating a score.
    assert "Docker, AWS, Git, Postgres" in rendered
    assert "backend, frontend, fullstack, SRE/infra/devops, data/ML, mobile, QA" in rendered
    assert "NEVER assume the candidate is mid-level" in rendered


def test_gating_criteria_reach_both_real_prompts() -> None:
    quick = render_quick_scoring_system_prompt()
    deep = render_deep_analysis_system_prompt()

    for shared in (
        "Docker, AWS, Git, Postgres",
        "backend, frontend, fullstack, SRE/infra/devops, data/ML, mobile, QA",
    ):
        assert shared in quick
        assert shared in deep


def test_quick_scoring_prompt_is_byte_stable_across_calls() -> None:
    """Anthropic prompt caching reuses this prefix across chunks and runs.
    Anything non-deterministic in its assembly silently destroys the cache hit
    rate without changing any output, so nothing would report the regression."""
    assert render_quick_scoring_system_prompt() == render_quick_scoring_system_prompt()


def test_verdict_prose_matches_the_banding_code() -> None:
    """The batch prompt quotes its thresholds in prose. If the constants move
    and the text does not, the model is told a different rule than the code
    applies."""
    quick = render_quick_scoring_system_prompt()

    assert f">= {STRONG_THRESHOLD}" in quick
    assert f"< {MODERATE_THRESHOLD}" in quick
    assert verdict_label(STRONG_THRESHOLD) == "strong"
    assert verdict_label(MODERATE_THRESHOLD) == "moderate"
    assert verdict_label(MODERATE_THRESHOLD - 0.01) == "weak"

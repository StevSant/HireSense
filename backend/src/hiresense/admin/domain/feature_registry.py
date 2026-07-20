from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureDescriptor:
    """Describes a single LLM-using feature for the admin override UI.

    `key` is the stable identifier used in: usage logs, override rows, and at
    every LLMPort call site. Never rename a key without a migration — the
    usage_log table is keyed by it.
    """

    key: str
    name: str
    description: str


# Single source of truth. Adding a new LLM-using feature only requires
# appending an entry here AND passing the same `key` from the call site.
FEATURE_REGISTRY: tuple[FeatureDescriptor, ...] = (
    FeatureDescriptor(
        key="cv_parser",
        name="CV Parser",
        description="Extracts structured profile data from uploaded PDF CVs.",
    ),
    FeatureDescriptor(
        key="profile_skill_extractor",
        name="Profile Skill Extractor",
        description="Extracts and normalizes skills from CV text.",
    ),
    FeatureDescriptor(
        key="application_skill_extractor",
        name="Job Description Parser",
        description="Extracts required skills from pasted/scraped job descriptions.",
    ),
    FeatureDescriptor(
        key="culture_scorer",
        name="Culture Scorer",
        description="Scores cultural fit between candidate and job description.",
    ),
    FeatureDescriptor(
        key="seniority_scorer",
        name="Seniority Scorer",
        description="Estimates seniority alignment.",
    ),
    FeatureDescriptor(
        key="compensation_scorer",
        name="Compensation Scorer",
        description="Reasons about compensation alignment.",
    ),
    FeatureDescriptor(
        key="growth_scorer",
        name="Growth Scorer",
        description="Estimates growth opportunity.",
    ),
    FeatureDescriptor(
        key="application_strength_scorer",
        name="Application Strength Scorer",
        description="Scores how strong the candidate's application would be.",
    ),
    FeatureDescriptor(
        key="interview_readiness_scorer",
        name="Interview Readiness Scorer",
        description="Scores how prepared the candidate is for interviews.",
    ),
    FeatureDescriptor(
        key="match_dimension_scorer",
        name="Combined Dimension Scorer",
        description=(
            "Scores seniority, compensation, growth, culture, application "
            "strength, and interview readiness in a single call. Default path "
            "for per-job dimension scoring; the 6 individual scorers above are "
            "the fallback when this response fails to parse."
        ),
    ),
    FeatureDescriptor(
        key="llm_scorer",
        name="LLM Match Scorer",
        description="Holistic LLM-driven match scoring.",
    ),
    FeatureDescriptor(
        key="matching_reasoning",
        name="Matching Reasoning",
        description="Generates pros/cons/recommendations for a match.",
    ),
    FeatureDescriptor(
        key="cv_optimizer",
        name="CV Optimizer",
        description="Rewrites the CV LaTeX to better fit a job.",
    ),
    FeatureDescriptor(
        key="cover_letter",
        name="Cover Letter Generator",
        description="Generates a tailored cover letter.",
    ),
    FeatureDescriptor(
        key="cv_translator",
        name="CV Translator",
        description="Translates a CV's LaTeX into another language, preserving commands.",
    ),
    FeatureDescriptor(
        key="interview_prep",
        name="Interview Prep",
        description="Generates competencies, technical topics, negotiation points.",
    ),
    FeatureDescriptor(
        key="company_research",
        name="Company Research",
        description="Analyzes companies for research notes.",
    ),
    FeatureDescriptor(
        key="match_quick_scorer",
        name="Quick Match Scorer",
        description=(
            "Fast, batched per-job match scoring shown on the job list. Gates on "
            "seniority overshoot, missing core skills, and role discipline. Use a "
            "cheap model here."
        ),
    ),
    FeatureDescriptor(
        key="match_deep_analyzer",
        name="Deep Match Analyzer",
        description=(
            "On-demand, single-job match analysis for the detail panel: dimension "
            "breakdown, matched/missing skills, pros/cons, recommendations, and a "
            "narrative. Use a strong model here."
        ),
    ),
)

_BY_KEY = {f.key: f for f in FEATURE_REGISTRY}


def get_feature(key: str) -> FeatureDescriptor | None:
    return _BY_KEY.get(key)


def all_feature_keys() -> tuple[str, ...]:
    return tuple(f.key for f in FEATURE_REGISTRY)

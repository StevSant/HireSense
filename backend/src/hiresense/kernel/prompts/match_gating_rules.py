from __future__ import annotations

import dataclasses

from hiresense.kernel.prompts.verdict_bands import MODERATE_THRESHOLD, STRONG_THRESHOLD

# The three gates that decide whether a candidate genuinely fits a job, as
# opposed to merely sharing keywords with it.
#
# This policy was stated twice — in ingestion's quick-scoring prompt and in
# matching's deep-analysis prompt — in different words and at different
# strictness. The quick prompt named the peripheral tools that must not lift a
# score and listed the disciplines to classify against; the deep prompt did
# neither, so the two tiers could reach opposite conclusions about the same job
# and the deep view would silently contradict the list it was opened from.
#
# What must agree is the DETECTION CRITERIA — what counts as a seniority
# mismatch, what counts as a core skill, which disciplines exist. What may
# legitimately differ is the CONSEQUENCE: the batch tier caps a numeric score so
# ranking stays consistent across thousands of jobs, while the single-job tier
# reasons in prose across its own named fields. So the criteria live here once
# and each tier supplies its own consequences.


@dataclasses.dataclass(frozen=True)
class GatingConsequences:
    """What a tier does when each gate trips, in that tier's own vocabulary."""

    seniority: str
    core_skill: str
    discipline: str
    closing: str


def render_gating_rules(consequences: GatingConsequences) -> str:
    """The three fit gates, with this tier's consequences spliced in."""
    return (
        "Apply these gating rules STRICTLY — they OVERRIDE topical/keyword overlap:\n"
        "1. SENIORITY GATING. Infer the candidate's level from their experience "
        "(years, scope, titles). If a job's seniority (Senior, Staff, Lead, "
        "Principal, Director, Head) is clearly ABOVE the candidate's level, "
        f"{consequences.seniority} "
        "NEVER assume the candidate is mid-level; infer it from the CV text.\n"
        "2. CORE-SKILL GATING. Identify the job's PRIMARY language / core discipline "
        "(e.g. Java for a Java Engineer; Go + Linux internals + on-call for an SRE). "
        f"If the candidate lacks that primary language or core discipline, "
        f"{consequences.core_skill} "
        "Shared peripheral tools (Docker, AWS, Git, Postgres) must NOT "
        "lift a score on their own.\n"
        "3. DISCIPLINE MATCH. Classify the job: backend, frontend, fullstack, "
        "SRE/infra/devops, data/ML, mobile, QA, or other. If it differs from the "
        f"candidate's primary discipline, {consequences.discipline}\n"
        f"{consequences.closing}"
    )


# Ingestion's batched list scoring. Numeric caps keep thousands of independently
# scored jobs on one comparable scale; the thresholds come from verdict_bands so
# the prose cannot drift from the banding code.
BATCH_SCORING_CONSEQUENCES = GatingConsequences(
    seniority=(
        'cap the score at 0.35 and add a dealbreaker like "Senior role — beyond your level".'
    ),
    core_skill=(
        'cap the score at 0.30 and add a dealbreaker naming it (e.g. "Requires Java — not in '
        'your stack").'
    ),
    discipline=(
        f"treat it as a weak fit (<= {MODERATE_THRESHOLD}) unless the "
        "CV shows direct hands-on experience in that discipline."
    ),
    closing=(
        f'4. Award "strong" (>= {STRONG_THRESHOLD}) ONLY when seniority fits AND the primary '
        f'skill and discipline match. Use "weak" (< {MODERATE_THRESHOLD}) whenever any gate '
        "trips.\n"
        "Keep each reason and dealbreaker to a short concrete phrase (~12 words max)."
    ),
)

# Matching's single-job deep analysis. No numeric caps: this tier writes prose
# across its own named fields and one narrative, so it states the consequence in
# terms of those fields instead.
DEEP_ANALYSIS_CONSEQUENCES = GatingConsequences(
    seniority="seniority_fit and overall_score must be low.",
    core_skill="skills_role_fit and overall_score must be low; list it under missing_skills.",
    discipline=(
        "treat it as a weak fit unless the CV shows direct hands-on experience in that discipline."
    ),
    closing="Be specific and concrete; recommendations should be actionable next steps.",
)

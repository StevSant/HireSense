from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class DimensionRubric:
    """What one matching dimension measures, declared once.

    The same six dimensions were described in two places: each individual
    scorer's `_build_prompt` spelled its criteria out as a bullet list, and
    CombinedDimensionScorer's system prompt restated all six as one-line
    summaries. The wording had already diverged — the combined prompt said
    culture_fit covered "collaboration style", the individual scorer asked for
    "team-oriented vs. solo" — while the two paths are drop-in replacements for
    each other, chosen at wiring time and feeding the same composite.

    `criteria` is the single source. Both prompt shapes render from it:
    inline() for the combined one-pass prompt, bulleted() for the individual
    scorer that owns that dimension.
    """

    name: str
    instruction: str
    criteria: tuple[str, ...]
    scale_high: str
    scale_low: str
    # Appended only where scoring is impossible without a CV.
    no_profile_note: str = ""

    def inline(self) -> str:
        """One-line form, for the combined all-dimensions-at-once prompt."""
        body = "; ".join(self.criteria)
        note = f" {self.no_profile_note}" if self.no_profile_note else ""
        return f"- {self.name}: {body}.{note}"

    def bulleted(self) -> str:
        """Instruction + bullets + scale, for this dimension's own scorer."""
        bullets = "\n".join(f"- {c}" for c in self.criteria)
        return (
            f"{self.instruction} Consider:\n"
            f"{bullets}\n"
            f"A score of 1.0 means {self.scale_high}; 0.0 means {self.scale_low}. "
            'Return JSON: {"score": <float>, "rationale": "<brief>"}.'
        )


SENIORITY_FIT = DimensionRubric(
    name="seniority_fit",
    instruction="Evaluate how well this role's seniority fits the candidate.",
    criteria=(
        "How the role's seniority matches the candidate's experience level",
        "Years, scope, and titles evidenced in the CV",
    ),
    scale_high="an excellent seniority match",
    scale_low="a badly mismatched level",
    no_profile_note="Assume a general mid-level engineer if no profile is given.",
)

COMPENSATION = DimensionRubric(
    name="compensation",
    instruction="Evaluate the compensation competitiveness of this role.",
    criteria=(
        "The salary range against market rates for the location and role level",
        "If no salary is specified, infer from company size, role, and location",
    ),
    scale_high="highly competitive pay",
    scale_low="well below market",
)

GROWTH_POTENTIAL = DimensionRubric(
    name="growth_potential",
    instruction="Evaluate the growth potential of this role.",
    criteria=(
        "Learning and skill development opportunities",
        "Modernity of the tech stack",
        "Mentorship and leadership exposure",
        "Career trajectory and advancement potential",
    ),
    scale_high="excellent growth prospects",
    scale_low="a stagnant/dead-end role",
)

CULTURE_FIT = DimensionRubric(
    name="culture_fit",
    instruction="Evaluate the culture fit of this role.",
    criteria=(
        "Remote, hybrid, or on-site flexibility",
        "Work-life balance signals in the description",
        "Collaboration style (team-oriented vs. solo)",
        "Company values and mission alignment",
    ),
    scale_high="excellent culture alignment",
    scale_low="a poor fit",
)

APPLICATION_STRENGTH = DimensionRubric(
    name="application_strength",
    instruction="Evaluate how well this candidate's CV positions them for the role.",
    criteria=(
        "Skill overlap between candidate and job requirements",
        "Relevance and quality of experience",
        "How compellingly the CV tells their story for this role",
    ),
    scale_high="the CV is an excellent match",
    scale_low="a very poor fit",
    no_profile_note="If no candidate profile is given, score 0.5 and say so.",
)

INTERVIEW_READINESS = DimensionRubric(
    name="interview_readiness",
    instruction="Evaluate this candidate's interview readiness for the role.",
    criteria=(
        "Availability of strong STAR (Situation, Task, Action, Result) story material",
        "Technical depth and hands-on evidence",
        "Potential weak spots an interviewer would probe",
    ),
    scale_high="the candidate is very well prepared",
    scale_low="they are unprepared",
    no_profile_note="If no candidate profile is given, score 0.5 and say so.",
)

# Order defines the JSON schema shown to the combined scorer's LLM. Names must
# match each BaseLLMScorer subclass's `dimension_name` exactly, since the
# combined scorer is a drop-in replacement for their fan-out.
ALL_DIMENSIONS: tuple[DimensionRubric, ...] = (
    SENIORITY_FIT,
    COMPENSATION,
    GROWTH_POTENTIAL,
    CULTURE_FIT,
    APPLICATION_STRENGTH,
    INTERVIEW_READINESS,
)

DIMENSION_NAMES: tuple[str, ...] = tuple(d.name for d in ALL_DIMENSIONS)

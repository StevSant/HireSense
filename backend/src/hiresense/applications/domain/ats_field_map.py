from __future__ import annotations

from hiresense.applications.domain.field_fill import FieldFill

# Canonical Apply Assist field key -> lowercase label substrings a client matches
# against an ATS form's visible field labels. Grounded in real Greenhouse / Lever
# / Ashby application forms, whose label wording is largely ATS-agnostic, so one
# shared map serves all of them; per-ATS overrides can be layered on later.
_LABEL_PATTERNS: dict[str, list[str]] = {
    "first_name": ["first name"],
    "last_name": ["last name"],
    "full_name": ["full name"],
    "preferred_name": ["preferred name", "preferred first name"],
    "email": ["email", "e-mail"],
    "phone": ["phone", "mobile", "telephone"],
    "location": ["location", "city", "current location", "where are you"],
    "linkedin_url": ["linkedin"],
    "github_url": ["github"],
    "portfolio_url": ["portfolio", "website", "personal site"],
    "work_authorization": ["work authorization", "authorized to work", "right to work"],
    "requires_visa_sponsorship": ["sponsorship", "visa", "require sponsorship"],
    "desired_salary": ["salary", "expected salary", "compensation expectation"],
    "years_of_experience": ["years of experience", "years experience"],
    "willing_to_relocate": ["relocate", "relocation"],
    "start_availability": ["availability", "start date", "notice period", "when can you start"],
}


def build_autofill_plan(ats_type: str | None, prefill: dict[str, object]) -> list[FieldFill]:
    """Turn a candidate's prefill values into per-field autofill instructions for
    an ATS form.

    Only ATS-form jobs are autofillable, so a falsy `ats_type` (a redirect or
    unknown job from Phase 0 classification) yields an empty plan. Output order
    is stable (label-map order) so clients and tests are deterministic.
    """
    if not ats_type:
        return []
    plan: list[FieldFill] = []
    for key, patterns in _LABEL_PATTERNS.items():
        if key in prefill:
            plan.append(
                FieldFill(
                    canonical_key=key,
                    value=prefill[key],
                    label_patterns=list(patterns),
                )
            )
    return plan

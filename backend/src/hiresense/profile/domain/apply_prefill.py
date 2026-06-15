from __future__ import annotations

from hiresense.profile.domain.models import CandidateProfile

# Canonical application-form field keys produced from a candidate profile. The
# Phase 2 autofill maps these onto each ATS form's real field names.


def _put(out: dict[str, object], key: str, value: str | None) -> None:
    """Add a stripped, non-empty string value under `key` (skip None/blank)."""
    if value is None:
        return
    cleaned = value.strip()
    if cleaned:
        out[key] = cleaned


def build_prefill(profile: CandidateProfile) -> dict[str, object]:
    """Map a CandidateProfile (+ its ApplyProfile answer bank) onto canonical
    application-form field keys, omitting anything we don't know.

    This is the pure brain of Apply Assist's autofill: given a profile it yields
    the values to drop into a detected ATS form. It performs no I/O.
    """
    out: dict[str, object] = {}

    full_name = (profile.name or "").strip()
    if full_name:
        out["full_name"] = full_name
        first, _, last = full_name.partition(" ")
        out["first_name"] = first
        last = last.strip()
        if last:
            out["last_name"] = last

    _put(out, "email", profile.email)
    _put(out, "phone", profile.phone)
    _put(out, "location", profile.location)
    _put(out, "linkedin_url", profile.linkedin_url)
    _put(out, "github_url", profile.github_url)
    _put(out, "portfolio_url", profile.portfolio_url)

    ap = profile.apply_profile
    if ap is not None:
        _put(out, "preferred_name", ap.preferred_name)
        _put(out, "work_authorization", ap.work_authorization)
        _put(out, "desired_salary", ap.desired_salary)
        _put(out, "start_availability", ap.start_availability)
        if ap.requires_visa_sponsorship is not None:
            out["requires_visa_sponsorship"] = ap.requires_visa_sponsorship
        if ap.years_of_experience is not None:
            out["years_of_experience"] = ap.years_of_experience
        if ap.willing_to_relocate is not None:
            out["willing_to_relocate"] = ap.willing_to_relocate

    return out

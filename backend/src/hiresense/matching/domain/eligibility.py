from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel

from hiresense.profile.domain.work_authorization import WorkAuthorizationStatus


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


class EligibilityResult(BaseModel):
    status: EligibilityStatus
    rationale: str


def determine_work_authorization_eligibility(job: Any, profile: Any | None) -> EligibilityResult:
    """Evaluate explicit sponsorship facts without inferring legal eligibility.

    This intentionally produces ``unknown`` whenever either side has not supplied
    enough structured information. Only an explicit sponsorship conflict is a
    hard stop for subjective matching.
    """
    candidate_status = _candidate_status(profile)
    requires_existing_authorization = _value(job, "requires_existing_work_authorization")
    sponsorship_available = _value(job, "visa_sponsorship_available")

    if candidate_status is WorkAuthorizationStatus.REQUIRES_SPONSORSHIP:
        if sponsorship_available is False:
            return EligibilityResult(
                status=EligibilityStatus.INELIGIBLE,
                rationale="The role explicitly does not offer visa sponsorship.",
            )
        if requires_existing_authorization is True:
            return EligibilityResult(
                status=EligibilityStatus.INELIGIBLE,
                rationale="The role requires existing work authorization.",
            )
        if sponsorship_available is True:
            return EligibilityResult(
                status=EligibilityStatus.ELIGIBLE,
                rationale="The role explicitly offers visa sponsorship.",
            )
        return EligibilityResult(
            status=EligibilityStatus.UNKNOWN,
            rationale="The role does not state a visa-sponsorship policy.",
        )

    if candidate_status is WorkAuthorizationStatus.AUTHORIZED:
        if requires_existing_authorization is True or sponsorship_available is False:
            return EligibilityResult(
                status=EligibilityStatus.ELIGIBLE,
                rationale="The candidate reports existing work authorization.",
            )
        return EligibilityResult(
            status=EligibilityStatus.UNKNOWN,
            rationale="The role does not state a work-authorization requirement.",
        )

    return EligibilityResult(
        status=EligibilityStatus.UNKNOWN,
        rationale="The candidate has not specified work-authorization status.",
    )


def _candidate_status(profile: Any | None) -> WorkAuthorizationStatus:
    apply_profile = getattr(profile, "apply_profile", None)
    if apply_profile is None:
        return WorkAuthorizationStatus.UNKNOWN

    status = getattr(apply_profile, "work_authorization_status", WorkAuthorizationStatus.UNKNOWN)
    if status != WorkAuthorizationStatus.UNKNOWN:
        return WorkAuthorizationStatus(status)

    # Existing profiles stored the boolean before the structured declaration.
    # Treat it as a compatibility input without guessing when it is absent.
    requires_sponsorship = getattr(apply_profile, "requires_visa_sponsorship", None)
    if requires_sponsorship is True:
        return WorkAuthorizationStatus.REQUIRES_SPONSORSHIP
    if requires_sponsorship is False:
        return WorkAuthorizationStatus.AUTHORIZED
    return WorkAuthorizationStatus.UNKNOWN


def _value(job: Any, name: str) -> Any:
    return job.get(name) if isinstance(job, dict) else getattr(job, name, None)

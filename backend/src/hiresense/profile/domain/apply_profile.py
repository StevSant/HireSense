from __future__ import annotations

from pydantic import BaseModel, Field

from hiresense.profile.domain.screening_answer import ScreeningAnswer
from hiresense.profile.domain.work_authorization import WorkAuthorizationStatus


class ApplyProfile(BaseModel):
    """One-per-person answer bank for the fields job-application forms ask for.

    These are the answers that don't change per CV language variant (work
    authorization, salary, reusable screening answers), so they are stored once
    and broadcast across all profile rows. The contact fields and links a form
    also needs (name, email, phone, location, linkedin/github/portfolio) already
    live on CandidateProfile and are combined by build_prefill — they are not
    duplicated here.
    """

    preferred_name: str | None = None
    work_authorization: str | None = None
    work_authorization_status: WorkAuthorizationStatus = WorkAuthorizationStatus.UNKNOWN
    requires_visa_sponsorship: bool | None = None
    desired_salary: str | None = None
    years_of_experience: int | None = None
    willing_to_relocate: bool | None = None
    start_availability: str | None = None
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list)

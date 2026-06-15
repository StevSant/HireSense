from __future__ import annotations

from pydantic import BaseModel

from hiresense.applications.domain.field_fill import FieldFill


class AutofillPlanView(BaseModel):
    """The one-call Apply Assist handoff bundle for an application: how to apply
    plus the per-field autofill instructions a client applies to the ATS form.

    `fills` is empty when the job isn't an ATS form (application_method is then
    'redirect' or 'unknown') or when the user has no profile data for any field.
    """

    application_method: str
    ats_type: str | None = None
    apply_url: str | None = None
    fills: list[FieldFill]

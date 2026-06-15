from __future__ import annotations

from pydantic import BaseModel

from hiresense.ingestion.domain.application_method import ApplicationMethod


class ApplicationClassification(BaseModel):
    """Result of classifying how a job is applied to (see classify_application).

    `apply_url` is set only when we are confident the URL is a direct application
    form (i.e. `ats_form`); for plain redirects it stays None until a later phase
    resolves the real apply destination.
    """

    apply_url: str | None = None
    application_method: ApplicationMethod = ApplicationMethod.UNKNOWN
    ats_type: str | None = None

from __future__ import annotations

from pydantic import BaseModel


class CompanyProfile(BaseModel):
    """Source-provided company profile captured at ingestion.

    Unlike LLM-synthesised research, these fields come straight from the job
    board / ATS (e.g. GetOnBoard's ``/companies/{id}`` payload). They ground the
    research prompt and can be surfaced even when no LLM is configured. All
    descriptive text is already plain (HTML stripped) and may be non-English.
    """

    company_name: str
    source: str
    description: str | None = None
    website: str | None = None
    headquarters: str | None = None

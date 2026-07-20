from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    company_name: str = Field(min_length=1)
    job_description: str = ""


class CompanyResearchResponse(BaseModel):
    id: uuid.UUID | None = None
    company_name: str
    funding_stage: str
    tech_stack: str
    culture_summary: str
    growth_trajectory: str
    red_flags: str | None
    pros: str
    cons: str
    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    website: str | None = None
    # Source-provided About text (plain text, may be non-English). Present when a
    # company profile was captured at ingestion; independent of LLM availability.
    description: str | None = None
    logo_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

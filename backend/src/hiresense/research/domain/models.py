from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CompanyResearch(BaseModel):
    """Domain model for cached company research (provider-agnostic)."""

    id: uuid.UUID | None = None
    company_name: str
    funding_stage: str
    tech_stack: str
    culture_summary: str
    growth_trajectory: str
    red_flags: str | None = None
    pros: str
    cons: str
    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    website: str | None = None
    raw_llm_response: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

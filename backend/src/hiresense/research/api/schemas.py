from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class ResearchRequest(BaseModel):
    company_name: str
    job_description: str = ""


class CompanyResearchResponse(BaseModel):
    id: uuid.UUID
    company_name: str
    funding_stage: str
    tech_stack: str
    culture_summary: str
    growth_trajectory: str
    red_flags: str | None
    pros: str
    cons: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

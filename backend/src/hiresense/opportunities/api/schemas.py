from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

from hiresense.opportunities.domain.models import OpportunityKind


class OpportunityResponse(BaseModel):
    id: uuid.UUID
    kind: OpportunityKind
    title: str
    organization: str
    url: str
    apply_url: str | None = None
    description: str = ""
    topics: list[str] = Field(default_factory=list)
    country: str | None = None
    city: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    cfp_deadline: date | None = None
    application_deadline: date | None = None
    funding: str | None = None
    source: str
    source_id: str = ""
    status: str = "open"
    source_metadata: dict = Field(default_factory=dict)
    relevance_score: float | None = None

    model_config = {"from_attributes": True}


class PaginatedOpportunitiesResponse(BaseModel):
    items: list[OpportunityResponse]
    total: int
    page: int
    page_size: int


class FetchOpportunitiesResponse(BaseModel):
    sources: dict
    inserted: int = 0
    updated: int = 0
    reopened: int = 0
    unchanged: int = 0
    errors: list = Field(default_factory=list)

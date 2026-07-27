from __future__ import annotations

import enum
import uuid as uuid_mod
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class OpportunityKind(str, enum.Enum):
    CONFERENCE = "conference"
    CFP = "cfp"
    GRANT = "grant"
    FELLOWSHIP = "fellowship"
    SUMMER_SCHOOL = "summer_school"
    EVENT = "event"


class RawOpportunity(BaseModel):
    """Raw payload from an opportunity source before normalization."""

    source: str
    source_id: str
    raw_data: dict[str, Any]


class Opportunity(BaseModel):
    """A non-job opportunity (conference, CFP, grant, funded event, …)."""

    id: uuid_mod.UUID | None = None
    kind: OpportunityKind = OpportunityKind.EVENT
    title: str
    organization: str = ""
    url: str = ""
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
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

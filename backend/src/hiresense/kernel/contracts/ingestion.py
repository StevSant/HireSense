from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from hiresense.kernel.events import DomainEvent


class NormalizedJobDTO(BaseModel):
    id: str
    title: str
    company: str
    description: str
    skills: list[str]
    location: str
    salary_range: str | None = None
    source: str
    source_type: str
    language: str
    url: str
    posted_date: datetime | None = None


class JobsIngestedEvent(DomainEvent):
    event_type: str = "jobs.ingested"
    payload: dict  # keys: job_ids (list[str]), source (str)

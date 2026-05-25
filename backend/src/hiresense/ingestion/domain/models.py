from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RawJobListing(BaseModel):
    source: str
    source_id: str
    raw_data: dict[str, Any]


class NormalizedJob(BaseModel):
    id: str
    title: str
    company: str
    description: str
    skills: list[str] = Field(default_factory=list)
    location: str = ""
    salary_range: str | None = None
    source: str
    source_type: str
    language: str = "en"
    url: str
    posted_date: datetime | None = None
    department: str | None = None
    platform: str | None = None
    categories: list[str] = Field(default_factory=list)
    match_score: float | None = None
    semantic_score: float | None = None

    def dedup_key(self) -> str:
        raw = f"{self.source}:{self.title.lower().strip()}:{self.company.lower().strip()}:{self.url}"
        return hashlib.sha256(raw.encode()).hexdigest()

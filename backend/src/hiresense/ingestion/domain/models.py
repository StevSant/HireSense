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
    # "remote" (fully remote), "hybrid", "on_site", or None if the source
    # doesn't expose it. Used by the strict-location filter to let through
    # only postings the candidate can actually take.
    remote_modality: str | None = None
    countries: list[str] = Field(default_factory=list)
    match_score: float | None = None
    semantic_score: float | None = None
    # Transient, per-request LLM scoring (populated by the quick scorer in the
    # list endpoint; not persisted on the job row — the durable store is the
    # job_match_cache table). `match_score` above mirrors `llm_score` when an
    # LLM score is available, else the heuristic skill+semantic blend.
    llm_score: float | None = None
    verdict: str | None = None
    reasons: list[str] = Field(default_factory=list)
    dealbreakers: list[str] = Field(default_factory=list)

    def dedup_key(self) -> str:
        raw = f"{self.source}:{self.title.lower().strip()}:{self.company.lower().strip()}:{self.url}"
        return hashlib.sha256(raw.encode()).hexdigest()

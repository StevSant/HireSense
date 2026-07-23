from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from hiresense.ingestion.domain.application_method import ApplicationMethod


class RawJobListing(BaseModel):
    source: str
    source_id: str
    raw_data: dict[str, Any]


class NormalizedJob(BaseModel):
    id: str
    source_id: str | None = None
    status: str = "open"
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
    # How the candidate applies, derived once at ingestion (see classify_application).
    # `apply_url` is a URL we're confident is a direct application form (set for
    # ats_form; None for plain redirects). `ats_type` is the detected ATS
    # (AtsPlatform value) when known. Defaults keep existing constructors valid.
    apply_url: str | None = None
    application_method: ApplicationMethod = ApplicationMethod.UNKNOWN
    ats_type: str | None = None
    posted_date: datetime | None = None
    # When the source declares an expiry (e.g. Himalayas' `expiryDate`), the job
    # is closed once now > expiry_date — a lifecycle signal for sources whose
    # public pages can't be URL-probed. None means "no declared expiry".
    expiry_date: datetime | None = None
    department: str | None = None
    platform: str | None = None
    categories: list[str] = Field(default_factory=list)
    # "remote" (fully remote), "hybrid", "on_site", or None if the source
    # doesn't expose it. Used by the strict-location filter to let through
    # only postings the candidate can actually take.
    remote_modality: str | None = None
    # Explicit job-posting facts only. ``None`` preserves the unknown state for
    # postings that do not say whether authorization or sponsorship is needed.
    requires_existing_work_authorization: bool | None = None
    visa_sponsorship_available: bool | None = None
    countries: list[str] = Field(default_factory=list)
    # Intrinsic, profile-independent quality classification computed once at
    # ingestion: "ok" | "low_quality" | "spam". Flagged jobs are hidden from the
    # listing by default (toggle to reveal). `quality_reason` is a short, human
    # explanation surfaced in the detail panel.
    quality: str = "ok"
    quality_reason: str | None = None
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
        raw = (
            f"{self.source}:{self.title.lower().strip()}:{self.company.lower().strip()}:{self.url}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

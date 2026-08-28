from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator

from hiresense.ingestion.domain.application_method import ApplicationMethod
from hiresense.ingestion.domain.apply_access import ApplyAccess
from hiresense.ingestion.domain.opportunity import (
    classify_opportunity_type,
    international_pathways,
)
from hiresense.ingestion.domain.source_capabilities import (
    source_apply_access,
    source_apply_access_note,
)


class RawJobListing(BaseModel):
    source: str = Field(min_length=1, max_length=50)
    source_id: str = Field(min_length=1, max_length=255)
    raw_data: dict[str, Any] = Field(min_length=1)
    fetch_metadata: "SourceFetchMetadata" = Field(default_factory=lambda: SourceFetchMetadata())

    @model_validator(mode="after")
    def normalize_identity(self) -> "RawJobListing":
        self.source = self.source.strip()
        self.source_id = self.source_id.strip()
        if not self.source or not self.source_id:
            raise ValueError("raw job listings require non-empty source and source_id")
        return self


class SourceFetchMetadata(BaseModel):
    """Optional adapter telemetry carried with each raw listing."""

    complete: bool = True
    pages_fetched: int = Field(default=1, ge=0)
    parser_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


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
    # Explicit employment classification when the source states it
    # (full_time / part_time / contract / internship / temporary / other).
    employment_type: str | None = None
    # Equity display string when the source states a range (e.g. "0.1% – 0.25%").
    equity_range: str | None = None
    # Platform-specific structured extras. Missing keys mean unknown — never invent.
    # May include salary_min/max/currency/period, yc_batch, company_stage, easy_apply,
    # employer_type, also_found_on, source_urls, etc.
    source_metadata: dict[str, Any] = Field(default_factory=dict)
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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def opportunity_type(self) -> str:
        """Normalized role type used by the opportunity filter and UI."""
        return classify_opportunity_type(self.employment_type, self.title, self.description).value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def international_pathways(self) -> list[str]:
        """Explicit routes that may make this posting useful internationally."""
        return international_pathways(
            visa_sponsorship_available=self.visa_sponsorship_available,
            remote_modality=self.remote_modality,
            countries=self.countries,
            location=self.location,
        )

    # Apply-access is a property of the *board*, not of the posting, so it is
    # resolved from the source capability registry at read time rather than
    # persisted. That keeps it correct for jobs ingested before the audit and
    # needs no migration when a board changes its policy.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def apply_access(self) -> ApplyAccess:
        return source_apply_access(self.source)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def apply_access_note(self) -> str:
        return source_apply_access_note(self.source)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def preferred_apply_url(self) -> str:
        """Best URL to send the candidate to.

        A confirmed ATS form wins, then a board-supplied direct application URL
        (Dice `applyUrl`, YC `applyUrl`, Arbeitnow's `/apply` hop), then the
        listing page. Anything that skips the aggregator's own apply hop is
        preferable — that hop is exactly where the walls live.
        """
        metadata_url = self.source_metadata.get("application_url")
        return self.apply_url or (metadata_url if isinstance(metadata_url, str) else "") or self.url

    def dedup_key(self) -> str:
        raw = (
            f"{self.source}:{self.title.lower().strip()}:{self.company.lower().strip()}:{self.url}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel

from hiresense.ingestion.domain.job_sort import sort_jobs
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.seniority import (
    SeniorityLevel,
    detect_seniority,
    extract_min_years,
)


class JobQueryParams(BaseModel):
    page: int = 1
    page_size: int = 20
    source: str | None = None
    keyword: str | None = None
    location: str | None = None
    skills: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    user_location: str | None = None
    strict_location: bool = False
    sort: str | None = None
    # Hide jobs whose match_score is below this threshold (0.0–1.0). When
    # None, no filter is applied. Jobs with match_score == None (not yet
    # scored, e.g. no profile) are passed through regardless. Jobs whose
    # semantic_score is still None are also exempt: their match_score is a
    # skill-only blend that semantic scoring hasn't had a chance to rescue
    # yet (see filter_and_paginate for the rationale).
    min_score: float | None = None
    # Seniority filter. When set, only jobs whose detected seniority is in
    # this set are returned. UNKNOWN passes through unless explicitly excluded.
    seniority_levels: list[SeniorityLevel] | None = None
    # When False (default), jobs with status == "closed" are hidden. Set True
    # to surface them (e.g. the frontend "Show closed" toggle).
    include_closed: bool = False
    # Maximum minimum-years-experience the user is willing to consider.
    # Jobs with no extractable years string pass through.
    max_years_experience: int | None = None


class PaginatedResult(BaseModel):
    jobs: list[NormalizedJob]
    total: int
    page: int
    page_size: int
    total_pages: int


def filter_and_paginate(
    jobs: list[NormalizedJob],
    params: JobQueryParams,
) -> PaginatedResult:
    filtered = jobs

    if not params.include_closed:
        filtered = [j for j in filtered if j.status != "closed"]

    if params.source:
        filtered = [j for j in filtered if j.source == params.source]

    if params.keyword:
        kw = params.keyword.lower()
        filtered = [
            j for j in filtered
            if kw in j.title.lower() or kw in j.description.lower()
        ]

    if params.location:
        loc = params.location.lower()
        filtered = [j for j in filtered if loc in j.location.lower()]

    if params.skills:
        skill_set = {s.strip().lower() for s in params.skills.split(",") if s.strip()}
        filtered = [
            j for j in filtered
            if skill_set & {s.lower() for s in j.skills}
        ]

    if params.date_from:
        filtered = [
            j for j in filtered
            if j.posted_date is not None and j.posted_date >= params.date_from
        ]

    if params.date_to:
        filtered = [
            j for j in filtered
            if j.posted_date is not None and j.posted_date <= params.date_to
        ]

    if params.min_score is not None:
        threshold = params.min_score
        # Only gate jobs that have a *fully computed* score. When semantic_score
        # is None the match_score is a skill-only blend (combine_fit_score falls
        # back to the skill side); culling on that would unfairly drop a
        # low-keyword / high-semantic job — e.g. verbose-tag sources like
        # getonboard suffer tag dilution on the skill side — before the
        # page-level semantic scoring pass can rescue it. Such jobs pass through
        # here and are gated, if at all, only once a real semantic score exists.
        filtered = [
            j for j in filtered
            if j.match_score is None
            or j.semantic_score is None
            or j.match_score >= threshold
        ]

    if params.seniority_levels:
        allowed = set(params.seniority_levels)
        filtered = [
            j for j in filtered
            if detect_seniority(j.title, j.description) in allowed
        ]

    if params.max_years_experience is not None:
        cap = params.max_years_experience
        filtered = [
            j for j in filtered
            if (extract_min_years(j.description) or 0) <= cap
        ]

    if params.strict_location and params.user_location:
        user_loc = params.user_location.strip().lower()
        open_keywords = ("worldwide", "anywhere", "global", "remote")

        def _matches_country(job: NormalizedJob) -> bool:
            # Fully-remote postings: treat as applyable from anywhere. Some
            # sources do restrict remote roles to specific countries, but
            # that's the minority — rather than false-reject, surface them
            # and let the user verify on the listing itself.
            if job.remote_modality == "remote":
                return True
            # Hybrid / on-site with a structured countries list: must be one
            # of those countries. The list is authoritative.
            if job.countries:
                return any(user_loc == c.strip().lower() for c in job.countries)
            # Free-text fallback for sources that don't expose structured
            # data (linkedin, hn_hiring, etc.).
            loc = (job.location or "").lower()
            if not loc:
                return True
            if any(kw in loc for kw in open_keywords):
                return True
            return user_loc in loc

        filtered = [j for j in filtered if _matches_country(j)]

    filtered = sort_jobs(filtered, params.sort)

    total = len(filtered)
    total_pages = math.ceil(total / params.page_size) if total > 0 else 0
    start = (params.page - 1) * params.page_size
    end = start + params.page_size
    page_jobs = filtered[start:end]

    return PaginatedResult(
        jobs=page_jobs,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
    )

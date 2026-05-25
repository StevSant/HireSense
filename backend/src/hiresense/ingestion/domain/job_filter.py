from __future__ import annotations

import math
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from hiresense.ingestion.domain.models import NormalizedJob

_DATETIME_MIN_UTC = datetime.min.replace(tzinfo=timezone.utc)


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

    if params.strict_location and params.user_location:
        user_loc = params.user_location.strip().lower()
        open_keywords = ("worldwide", "anywhere", "global")

        def _is_open(job_location: str) -> bool:
            if not job_location:
                return True
            loc = job_location.lower()
            if any(kw in loc for kw in open_keywords):
                return True
            return user_loc in loc

        filtered = [j for j in filtered if _is_open(j.location)]

    if params.sort == "match_desc":
        filtered = sorted(
            filtered,
            key=lambda j: (j.match_score if j.match_score is not None else -1.0),
            reverse=True,
        )
    elif params.sort == "date_desc":
        filtered = sorted(
            filtered,
            key=lambda j: j.posted_date or _DATETIME_MIN_UTC,
            reverse=True,
        )

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

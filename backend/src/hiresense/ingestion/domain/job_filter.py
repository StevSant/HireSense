from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from hiresense.ingestion.domain.job_sort import sort_jobs
from hiresense.ingestion.domain.opportunity import (
    InternationalPathway,
    OpportunityType,
    classify_opportunity_type,
    international_pathways,
)
from hiresense.shared.kernel import as_utc
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
    company: str | None = None
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
    # scored, e.g. no profile) are passed through because there is no score
    # against which to apply a profile-dependent threshold.
    min_score: float | None = None
    # Seniority filter. When set, only jobs whose detected seniority is in
    # this set are returned. UNKNOWN passes through unless explicitly excluded.
    seniority_levels: list[SeniorityLevel] | None = None
    # When False (default), jobs with status == "closed" are hidden. Set True
    # to surface them (e.g. the frontend "Show closed" toggle).
    include_closed: bool = False
    # When False (default), jobs flagged quality != "ok" (low_quality / spam)
    # are hidden. Set True to surface them (the "Show low-quality" toggle).
    include_low_quality: bool = False
    # Maximum minimum-years-experience the user is willing to consider.
    # Jobs with no extractable years string pass through.
    max_years_experience: int | None = None
    # Hide jobs whose posted_date is older than this many days (stale / re-
    # surfaced postings). None or <= 0 disables the filter. Jobs with no
    # posted_date are never hidden (unknown age).
    max_age_days: int | None = None
    # Derived opportunity lens. These filters intentionally run in Python
    # because they combine source fields and conservative title detection.
    opportunity_type: OpportunityType | None = None
    international_pathway: InternationalPathway | None = None


class PaginatedResult(BaseModel):
    jobs: list[NormalizedJob]
    total: int
    page: int
    page_size: int
    total_pages: int
    # Per-job count of imported LinkedIn connections at the job's company
    # (normalized match). Only jobs with at least one connection appear.
    connections_by_job: dict[str, int] = {}


def filter_and_paginate(
    jobs: list[NormalizedJob],
    params: JobQueryParams,
) -> PaginatedResult:
    filtered = jobs

    if not params.include_closed:
        filtered = [j for j in filtered if j.status != "closed"]

    if not params.include_low_quality:
        filtered = [j for j in filtered if (j.quality or "ok") == "ok"]

    if params.source:
        filtered = [j for j in filtered if j.source == params.source]

    if params.company:
        target = params.company.strip().lower()
        filtered = [j for j in filtered if j.company.strip().lower() == target]

    if params.keyword:
        kw = params.keyword.lower()
        filtered = [j for j in filtered if kw in j.title.lower() or kw in j.description.lower()]

    if params.location:
        loc = params.location.lower()
        filtered = [j for j in filtered if loc in j.location.lower()]

    if params.skills:
        skill_set = {s.strip().lower() for s in params.skills.split(",") if s.strip()}
        filtered = [j for j in filtered if skill_set & {s.lower() for s in j.skills}]

    # Both sides are normalised: query params arrive naive, stored posted_date
    # is aware, and comparing them raises TypeError (a 500 on the Date From
    # filter). Jobs with no posted_date stay excluded, as before.
    if params.date_from:
        date_from = as_utc(params.date_from)
        filtered = [
            j
            for j in filtered
            if date_from is not None and (p := as_utc(j.posted_date)) is not None and p >= date_from
        ]

    if params.date_to:
        date_to = as_utc(params.date_to)
        filtered = [
            j
            for j in filtered
            if date_to is not None and (p := as_utc(j.posted_date)) is not None and p <= date_to
        ]

    if params.min_score is not None:
        threshold = params.min_score
        # Apply the floor to every persisted score. The old semantic-score
        # exemption allowed clearly irrelevant jobs to leak into the default
        # list indefinitely, especially after a score-only sort or restart.
        # Jobs with no score still pass so a profile can be added later.
        filtered = [j for j in filtered if j.match_score is None or j.match_score >= threshold]

    if params.seniority_levels:
        allowed = set(params.seniority_levels)
        filtered = [j for j in filtered if detect_seniority(j.title, j.description) in allowed]

    if params.max_years_experience is not None:
        cap = params.max_years_experience
        filtered = [j for j in filtered if (extract_min_years(j.description) or 0) <= cap]

    if params.opportunity_type:
        filtered = [
            j
            for j in filtered
            if classify_opportunity_type(j.employment_type, j.title, j.description)
            == params.opportunity_type
        ]

    if params.international_pathway:
        filtered = [
            j
            for j in filtered
            if params.international_pathway.value
            in international_pathways(
                visa_sponsorship_available=j.visa_sponsorship_available,
                remote_modality=j.remote_modality,
                countries=j.countries,
                location=j.location,
            )
        ]

    if params.max_age_days is not None and params.max_age_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=params.max_age_days)

        def _fresh_enough(job: NormalizedJob) -> bool:
            posted = job.posted_date
            if posted is None:
                return True  # unknown age — never hide
            # Normalise naive datetimes (some sources) to UTC before comparing.
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            return posted >= cutoff

        filtered = [j for j in filtered if _fresh_enough(j)]

    if params.strict_location and params.user_location:
        user_loc = params.user_location.strip().lower()
        # Genuinely-open remote keywords. NOTE: bare "remote" is deliberately
        # NOT here — a posting can be "remote" yet restricted to a country
        # ("Remote (US)"), so the word "remote" alone never implies worldwide.
        open_keywords = ("worldwide", "anywhere", "global")
        # Parenthetical qualifiers that describe a work-mode / employment-type
        # rather than a geographic restriction. These must NOT exclude an
        # otherwise-worldwide remote role (e.g. "100% Remote (Full-time)").
        non_geo_qualifiers = (
            "remote",
            "onsite",
            "on-site",
            "on site",
            "hybrid",
            "full",
            "part",
            "contract",
            "freelance",
            "permanent",
            "temporary",
            "intern",
        )

        def _matches_country(job: NormalizedJob) -> bool:
            # Remote roles restricted to specific countries must honor that
            # restriction — e.g. getonbrd "remote_local" surfaces as
            # "Remote (Chile)" with countries=["Chile"]; an Ecuador user can't
            # apply, so don't show it. A remote role with NO country list is
            # worldwide → applyable from anywhere.
            if job.remote_modality == "remote":
                if job.countries:
                    return any(user_loc == c.strip().lower() for c in job.countries)
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
            # The user's own country named anywhere in the text → applyable.
            if user_loc in loc:
                return True
            # Genuinely-open remote → applyable from anywhere.
            if any(kw in loc for kw in open_keywords):
                return True
            # A geographic qualifier in parentheses restricts the role to that
            # place, even when it's remote: boards write "Remote (US)",
            # "REMOTE (US) or San Diego", "NYC or Remote (US)". The user's
            # country wasn't matched above, so such a role isn't applyable.
            # Qualifiers that are open keywords ("(Global)") or pure work-mode /
            # employment tags ("(Full-time)", "(Remote)") are not restrictions.
            #
            # An explicit parenthetical geo-lock is the ONLY thing that hides a
            # free-text-location job. A bare location string ("United States",
            # "New York, NY") is NOT treated as a hard restriction: sources like
            # linkedin/hn_hiring let you submit an application internationally
            # even when the listing names a foreign city, so the "jobs I can
            # apply to" filter keeps them. Structured remote/country data (the
            # branches above) is still authoritative — that's the explicit lock.
            for qualifier in re.findall(r"\(([^)]*)\)", loc):
                q = qualifier.strip()
                if not q:
                    continue
                if any(kw in q for kw in open_keywords):
                    continue
                if any(kw in q for kw in non_geo_qualifiers):
                    continue
                return False
            # No explicit parenthetical geo-lock → applyable (bare "remote",
            # bare foreign city, etc. all pass for unstructured sources).
            return True

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

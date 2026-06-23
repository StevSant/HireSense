from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hiresense.ingestion.domain.job_filter import JobQueryParams, filter_and_paginate
from hiresense.ingestion.domain.models import NormalizedJob


def _job(
    id: str = "1",
    title: str = "Engineer",
    company: str = "Co",
    source: str = "remotive",
    source_type: str = "api",
    location: str = "Remote",
    skills: list[str] | None = None,
    posted_date: datetime | None = None,
    description: str = "Do stuff",
    url: str = "https://example.com",
    remote_modality: str | None = None,
    countries: list[str] | None = None,
    status: str = "open",
    match_score: float | None = None,
    semantic_score: float | None = None,
    quality: str = "ok",
) -> NormalizedJob:
    return NormalizedJob(
        id=id,
        title=title,
        company=company,
        description=description,
        skills=skills or [],
        location=location,
        source=source,
        source_type=source_type,
        url=url,
        posted_date=posted_date,
        remote_modality=remote_modality,
        countries=countries or [],
        status=status,
        match_score=match_score,
        semantic_score=semantic_score,
        quality=quality,
    )


def test_paginate_first_page() -> None:
    jobs = [_job(id=str(i)) for i in range(50)]
    params = JobQueryParams(page=1, page_size=20)
    result = filter_and_paginate(jobs, params)
    assert len(result.jobs) == 20
    assert result.total == 50
    assert result.page == 1
    assert result.page_size == 20
    assert result.total_pages == 3


def test_paginate_last_page() -> None:
    jobs = [_job(id=str(i)) for i in range(50)]
    params = JobQueryParams(page=3, page_size=20)
    result = filter_and_paginate(jobs, params)
    assert len(result.jobs) == 10
    assert result.page == 3


def test_filter_by_source() -> None:
    jobs = [
        _job(id="1", source="remotive"),
        _job(id="2", source="linkedin"),
        _job(id="3", source="remotive"),
    ]
    params = JobQueryParams(source="remotive")
    result = filter_and_paginate(jobs, params)
    assert result.total == 2
    assert all(j.source == "remotive" for j in result.jobs)


def test_filter_by_keyword_in_title() -> None:
    jobs = [
        _job(id="1", title="Backend Engineer"),
        _job(id="2", title="Designer"),
    ]
    params = JobQueryParams(keyword="engineer")
    result = filter_and_paginate(jobs, params)
    assert result.total == 1
    assert result.jobs[0].title == "Backend Engineer"


def test_filter_by_keyword_in_description() -> None:
    jobs = [
        _job(id="1", title="Role", description="We need a Python expert"),
        _job(id="2", title="Role", description="Marketing position"),
    ]
    params = JobQueryParams(keyword="python")
    result = filter_and_paginate(jobs, params)
    assert result.total == 1


def test_filter_by_location() -> None:
    jobs = [
        _job(id="1", location="San Francisco, CA"),
        _job(id="2", location="Remote"),
        _job(id="3", location="Remote, US"),
    ]
    params = JobQueryParams(location="remote")
    result = filter_and_paginate(jobs, params)
    assert result.total == 2


def test_filter_by_skills() -> None:
    jobs = [
        _job(id="1", skills=["python", "fastapi"]),
        _job(id="2", skills=["react", "typescript"]),
        _job(id="3", skills=["python", "django"]),
    ]
    params = JobQueryParams(skills="python")
    result = filter_and_paginate(jobs, params)
    assert result.total == 2


def test_filter_by_multiple_skills() -> None:
    jobs = [
        _job(id="1", skills=["python", "fastapi"]),
        _job(id="2", skills=["react", "typescript"]),
        _job(id="3", skills=["python", "django"]),
    ]
    params = JobQueryParams(skills="python,react")
    result = filter_and_paginate(jobs, params)
    assert result.total == 3


def test_filter_by_date_range() -> None:
    jobs = [
        _job(id="1", posted_date=datetime(2026, 4, 1)),
        _job(id="2", posted_date=datetime(2026, 4, 5)),
        _job(id="3", posted_date=datetime(2026, 4, 10)),
        _job(id="4", posted_date=None),
    ]
    params = JobQueryParams(
        date_from=datetime(2026, 4, 3),
        date_to=datetime(2026, 4, 8),
    )
    result = filter_and_paginate(jobs, params)
    assert result.total == 1
    assert result.jobs[0].id == "2"


def test_combined_filters_and_pagination() -> None:
    jobs = [
        _job(id=str(i), source="remotive", location="Remote", skills=["python"])
        for i in range(30)
    ] + [
        _job(id=str(i + 30), source="linkedin", location="NYC")
        for i in range(20)
    ]
    params = JobQueryParams(source="remotive", page=1, page_size=20)
    result = filter_and_paginate(jobs, params)
    assert result.total == 30
    assert len(result.jobs) == 20
    assert result.total_pages == 2


def test_empty_result() -> None:
    params = JobQueryParams(source="nonexistent")
    result = filter_and_paginate([], params)
    assert result.total == 0
    assert result.jobs == []
    assert result.total_pages == 0


def test_job_query_params_defaults_for_location_match() -> None:
    params = JobQueryParams()
    assert params.user_location is None
    assert params.strict_location is False


def test_job_query_params_accepts_location_match_fields() -> None:
    params = JobQueryParams(user_location="Chile", strict_location=True)
    assert params.user_location == "Chile"
    assert params.strict_location is True


def test_strict_location_off_is_no_op() -> None:
    jobs = [
        _job(id="1", location="Remote (Remote)"),
        _job(id="2", location="Chile"),
        _job(id="3", location="USA only"),
    ]
    params = JobQueryParams(user_location="Chile", strict_location=False)
    result = filter_and_paginate(jobs, params)
    assert result.total == 3


def test_strict_location_requires_user_location_set() -> None:
    jobs = [_job(id="1", location="USA only"), _job(id="2", location="Chile")]
    params = JobQueryParams(user_location=None, strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 2


def test_strict_location_includes_empty_location() -> None:
    jobs = [_job(id="1", location="")]
    params = JobQueryParams(user_location="Chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 1


def test_strict_location_includes_worldwide_keywords() -> None:
    jobs = [
        _job(id="1", location="Worldwide"),
        _job(id="2", location="Remote - Anywhere"),
        _job(id="3", location="Global remote"),
    ]
    params = JobQueryParams(user_location="Chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 3


def test_strict_location_includes_user_country_substring() -> None:
    jobs = [
        _job(id="1", location="Chile"),
        _job(id="2", location="Chile (Remote)"),
        _job(id="3", location="Latin America - Chile, Peru"),
    ]
    params = JobQueryParams(user_location="Chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 3


def test_strict_location_keeps_bare_free_text_foreign_location() -> None:
    """Bare free-text foreign locations (no explicit parenthetical geo-lock) are
    applyable: sources like linkedin/hn_hiring accept international applications
    even when the listing names a foreign place. Only an explicit "(Country)"
    qualifier — or a structured countries list — hides such a job."""
    jobs = [
        _job(id="1", location="United States"),
        _job(id="2", location="New York, NY"),
        _job(id="3", location="USA only"),
        _job(id="4", location="Remote (US)"),  # explicit geo-lock → hidden
    ]
    params = JobQueryParams(user_location="Ecuador", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert {j.id for j in result.jobs} == {"1", "2", "3"}


def test_low_quality_hidden_by_default_and_revealed_by_toggle() -> None:
    jobs = [
        _job(id="ok", quality="ok"),
        _job(id="spam", quality="spam"),
        _job(id="low", quality="low_quality"),
    ]
    # Default: only the OK job shows.
    assert {j.id for j in filter_and_paginate(jobs, JobQueryParams()).jobs} == {"ok"}
    # Toggle on: everything shows.
    revealed = filter_and_paginate(jobs, JobQueryParams(include_low_quality=True)).jobs
    assert {j.id for j in revealed} == {"ok", "spam", "low"}


def test_max_age_days_hides_stale_jobs() -> None:
    """Jobs older than max_age_days are hidden; recent jobs and jobs with an
    unknown (None) posted_date are kept."""
    now = datetime.now(timezone.utc)
    jobs = [
        _job(id="old", posted_date=now - timedelta(days=400)),  # > 1 year → hidden
        _job(id="fresh", posted_date=now - timedelta(days=10)),  # recent → shown
        _job(id="unknown", posted_date=None),  # unknown age → shown
    ]
    params = JobQueryParams(max_age_days=365)
    result = filter_and_paginate(jobs, params)
    assert {j.id for j in result.jobs} == {"fresh", "unknown"}


def test_max_age_days_disabled_when_zero_or_none() -> None:
    now = datetime.now(timezone.utc)
    jobs = [_job(id="old", posted_date=now - timedelta(days=400))]
    assert {j.id for j in filter_and_paginate(jobs, JobQueryParams()).jobs} == {"old"}
    assert {j.id for j in filter_and_paginate(jobs, JobQueryParams(max_age_days=0)).jobs} == {"old"}


def test_max_age_days_handles_naive_posted_date() -> None:
    # Some sources yield tz-naive datetimes; the filter must not crash on them.
    old_naive = datetime.now() - timedelta(days=400)
    jobs = [_job(id="old", posted_date=old_naive)]
    result = filter_and_paginate(jobs, JobQueryParams(max_age_days=365))
    assert result.jobs == []


def test_strict_location_remote_honors_country_restriction() -> None:
    """Worldwide remote passes; remote *restricted* to specific countries is
    honored — e.g. getonbrd 'remote_local' surfaces as "Remote (Chile)" with
    countries=["Chile"], and must be hidden for a user outside that list."""
    jobs = [
        _job(id="1", location="USA only"),  # bare free-text, no parenthetical lock
        _job(id="2", location="Remote"),  # free-text worldwide remote → passes
        _job(id="3", remote_modality="remote", countries=["Argentina"]),  # remote, AR-only
        _job(id="4", remote_modality="remote", countries=["Chile"]),  # remote, CL-only
        _job(id="5", remote_modality="remote", countries=[]),  # remote, worldwide
    ]
    params = JobQueryParams(user_location="Chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    # AR-only remote (id=3) is excluded for a Chile user — a structured countries
    # list is an explicit geo-lock. The bare free-text "USA only" (id=1) now
    # passes (no parenthetical qualifier), alongside worldwide remote (2, 5) and
    # Chile-restricted remote (4).
    assert {j.id for j in result.jobs} == {"1", "2", "4", "5"}


def test_strict_location_excludes_country_qualified_free_text_remote() -> None:
    """Free-text remote roles qualified to a specific country ("Remote (US)")
    are NOT worldwide — an out-of-country user can't apply, so they're hidden.
    This is the hn_hiring / linkedin case: no structured countries list, the
    restriction lives in the location text's parenthetical qualifier."""
    jobs = [
        _job(id="1", location="Remote (US)"),
        _job(id="2", location="REMOTE (US) or San Diego"),
        _job(id="3", location="NYC or Remote (US)"),
        _job(id="4", location="Remote (United States)"),
        # Genuinely worldwide remote → still shown.
        _job(id="5", location="100% REMOTE (Global)"),
        _job(id="6", location="Remote (Global)"),
        _job(id="7", location="Remote"),
        # Work-mode / employment qualifier is not a geographic restriction.
        _job(id="8", location="100% Remote (Full-time)"),
    ]
    params = JobQueryParams(user_location="Ecuador", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert {j.id for j in result.jobs} == {"5", "6", "7", "8"}


def test_strict_location_keeps_country_qualified_remote_for_local_user() -> None:
    """A remote role qualified to the user's own country is applyable."""
    jobs = [
        _job(id="1", location="Remote (Ecuador)"),
        _job(id="2", location="Remote (US)"),
    ]
    params = JobQueryParams(user_location="Ecuador", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert {j.id for j in result.jobs} == {"1"}


def test_strict_location_hybrid_requires_country_match() -> None:
    jobs = [
        _job(id="1", remote_modality="hybrid", countries=["Chile"]),
        _job(id="2", remote_modality="hybrid", countries=["Argentina"]),
        _job(id="3", remote_modality="on_site", countries=["Chile", "Peru"]),
    ]
    params = JobQueryParams(user_location="chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert {j.id for j in result.jobs} == {"1", "3"}


def test_strict_location_case_insensitive() -> None:
    jobs = [
        _job(id="1", location="CHILE"),
        _job(id="2", location="chile"),
        _job(id="3", location="WORLDWIDE"),
    ]
    params = JobQueryParams(user_location="chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 3


def test_strict_location_trims_user_location() -> None:
    # id=2 uses an explicit parenthetical geo-lock so it stays excluded under the
    # "only hide explicit geo-locks" rule; id=1 matches only once the padded
    # user_location is trimmed to "chile".
    jobs = [_job(id="1", location="Chile"), _job(id="2", location="Remote (USA)")]
    params = JobQueryParams(user_location="  Chile  ", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 1
    assert result.jobs[0].location == "Chile"


def test_closed_hidden_by_default() -> None:
    jobs = [_job(id="1", status="open"), _job(id="2", status="closed")]
    out = filter_and_paginate(jobs, JobQueryParams())
    assert out.total == 1
    assert all(j.status == "open" for j in out.jobs)


def test_include_closed_shows_all() -> None:
    jobs = [_job(id="1", status="open"), _job(id="2", status="closed")]
    out = filter_and_paginate(jobs, JobQueryParams(include_closed=True))
    assert out.total == 2


def test_min_score_gates_fully_scored_jobs() -> None:
    """A job with a real (semantic-backed) score below the threshold is culled."""
    jobs = [
        _job(id="low", match_score=0.2, semantic_score=0.15),
        _job(id="high", match_score=0.8, semantic_score=0.9),
    ]
    out = filter_and_paginate(jobs, JobQueryParams(min_score=0.5))
    assert {j.id for j in out.jobs} == {"high"}


def test_min_score_exempts_unscored_jobs() -> None:
    """match_score == None means never-scored: always passes the gate."""
    jobs = [_job(id="1", match_score=None, semantic_score=None)]
    out = filter_and_paginate(jobs, JobQueryParams(min_score=0.5))
    assert out.total == 1


def test_min_score_exempts_jobs_without_semantic_score() -> None:
    """Regression for #39: a low skill-only blend (no semantic score yet) must
    survive the gate so the page-level semantic pass can rescue it.

    Mirrors a verbose-tag source (e.g. getonboard) whose skill-overlap score is
    diluted to a low value but whose semantic fit hasn't been computed on the
    first request after restart / passthrough pre-ranking.
    """
    jobs = [
        _job(id="getonboard", match_score=0.1, semantic_score=None),
        _job(id="culled", match_score=0.1, semantic_score=0.1),
    ]
    out = filter_and_paginate(jobs, JobQueryParams(min_score=0.5))
    assert {j.id for j in out.jobs} == {"getonboard"}


def test_company_filter_is_exact_and_case_insensitive() -> None:
    jobs = [
        _job(id="1", company="Coderslab.io"),
        _job(id="2", company="coderslab.io"),
        _job(id="3", company="Coderslab LATAM"),
        _job(id="4", company="Other Co"),
    ]
    params = JobQueryParams(company="  CODERSLAB.IO ")
    result = filter_and_paginate(jobs, params)
    assert {j.id for j in result.jobs} == {"1", "2"}  # trimmed, case-insensitive, exact

from __future__ import annotations

from datetime import datetime

import pytest

from hiresense.ingestion.domain.job_filter import JobQueryParams, PaginatedResult, filter_and_paginate
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


def test_strict_location_excludes_non_matching() -> None:
    jobs = [
        _job(id="1", location="USA only"),
        _job(id="2", location="Europe"),
    ]
    params = JobQueryParams(user_location="Chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert result.total == 0


def test_strict_location_passes_remote_jobs() -> None:
    """Fully-remote postings should be applyable regardless of country."""
    jobs = [
        _job(id="1", location="USA only"),
        _job(id="2", location="Remote"),
        _job(id="3", remote_modality="remote", countries=["Argentina"]),
    ]
    params = JobQueryParams(user_location="Chile", strict_location=True)
    result = filter_and_paginate(jobs, params)
    assert {j.id for j in result.jobs} == {"2", "3"}


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
    jobs = [_job(id="1", location="Chile"), _job(id="2", location="USA")]
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

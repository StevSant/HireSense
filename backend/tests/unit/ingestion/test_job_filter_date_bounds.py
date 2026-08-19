from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain.job_filter import JobQueryParams, filter_and_paginate
from hiresense.ingestion.domain.job_list_criteria import JobListCriteria
from hiresense.ingestion.domain.models import NormalizedJob


def _job(job_id: str, posted: datetime | None) -> NormalizedJob:
    return NormalizedJob(
        id=job_id,
        title="Engineer",
        company="Acme",
        description="D",
        source="linkedin",
        source_type="api",
        url=f"https://example.com/{job_id}",
        posted_date=posted,
    )


def _params(**kwargs) -> JobQueryParams:
    return JobQueryParams(page=1, page_size=20, **kwargs)


def test_naive_date_from_does_not_raise_against_aware_posted_date() -> None:
    """Reproduces the 500 on the Date From filter.

    FastAPI parses ``?date_from=2026-08-01`` to a NAIVE datetime while stored
    posted_date values are timezone-aware; comparing them raised TypeError.
    """
    jobs = [
        _job("old", datetime(2026, 7, 1, tzinfo=timezone.utc)),
        _job("new", datetime(2026, 8, 15, tzinfo=timezone.utc)),
    ]

    result = filter_and_paginate(jobs, _params(date_from=datetime(2026, 8, 1)))

    assert [j.id for j in result.jobs] == ["new"]


def test_naive_date_to_does_not_raise_against_aware_posted_date() -> None:
    jobs = [
        _job("old", datetime(2026, 7, 1, tzinfo=timezone.utc)),
        _job("new", datetime(2026, 8, 15, tzinfo=timezone.utc)),
    ]

    result = filter_and_paginate(jobs, _params(date_to=datetime(2026, 8, 1)))

    assert [j.id for j in result.jobs] == ["old"]


def test_aware_bound_against_naive_posted_date_also_works() -> None:
    """The mirror case: some feeds omit an offset, so posted_date can be naive."""
    jobs = [_job("naive", datetime(2026, 8, 15))]

    result = filter_and_paginate(jobs, _params(date_from=datetime(2026, 8, 1, tzinfo=timezone.utc)))

    assert [j.id for j in result.jobs] == ["naive"]


def test_jobs_without_a_posted_date_stay_excluded() -> None:
    jobs = [_job("undated", None)]

    result = filter_and_paginate(jobs, _params(date_from=datetime(2026, 8, 1)))

    assert result.jobs == []


def test_criteria_matches_handles_mixed_awareness() -> None:
    criteria = JobListCriteria(date_from=datetime(2026, 8, 1))

    assert criteria.matches(_job("new", datetime(2026, 8, 15, tzinfo=timezone.utc))) is True
    assert criteria.matches(_job("old", datetime(2026, 7, 1, tzinfo=timezone.utc))) is False
    assert criteria.matches(_job("undated", None)) is False

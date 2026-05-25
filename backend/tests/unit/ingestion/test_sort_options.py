from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain.job_filter import JobQueryParams, filter_and_paginate
from hiresense.ingestion.domain.models import NormalizedJob


def _job(id: str, score: float | None = None, date: datetime | None = None) -> NormalizedJob:
    return NormalizedJob(
        id=id,
        title="x",
        company="x",
        description="x",
        skills=[],
        source="x",
        source_type="api",
        url="x",
        match_score=score,
        posted_date=date,
    )


def test_sort_match_desc_orders_by_score() -> None:
    jobs = [_job("a", 0.3), _job("b", 0.9), _job("c", 0.6)]
    result = filter_and_paginate(jobs, JobQueryParams(sort="match_desc"))
    assert [j.id for j in result.jobs] == ["b", "c", "a"]


def test_sort_match_desc_places_none_scores_last() -> None:
    jobs = [_job("a", None), _job("b", 0.9), _job("c", None), _job("d", 0.3)]
    result = filter_and_paginate(jobs, JobQueryParams(sort="match_desc"))
    assert [j.id for j in result.jobs[:2]] == ["b", "d"]
    assert set(j.id for j in result.jobs[2:]) == {"a", "c"}


def test_sort_date_desc_orders_by_posted_date() -> None:
    jobs = [
        _job("old", date=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _job("new", date=datetime(2026, 5, 1, tzinfo=timezone.utc)),
        _job("mid", date=datetime(2026, 3, 1, tzinfo=timezone.utc)),
    ]
    result = filter_and_paginate(jobs, JobQueryParams(sort="date_desc"))
    assert [j.id for j in result.jobs] == ["new", "mid", "old"]


def test_sort_date_desc_places_none_dates_last() -> None:
    jobs = [
        _job("nodate"),
        _job("dated", date=datetime(2026, 5, 1, tzinfo=timezone.utc)),
    ]
    result = filter_and_paginate(jobs, JobQueryParams(sort="date_desc"))
    assert [j.id for j in result.jobs] == ["dated", "nodate"]


def test_no_sort_preserves_order() -> None:
    jobs = [_job("a", 0.3), _job("b", 0.9), _job("c", 0.6)]
    result = filter_and_paginate(jobs, JobQueryParams())
    assert [j.id for j in result.jobs] == ["a", "b", "c"]

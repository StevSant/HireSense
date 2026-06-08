from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain import sort_jobs
from hiresense.ingestion.domain.models import NormalizedJob


def _job(id: str, *, score=None, date=None, title="", company="", location="", source="x"):
    return NormalizedJob(
        id=id, title=title, company=company, description="x", skills=[],
        location=location, source=source, source_type="api", url="x",
        match_score=score, posted_date=date,
    )


def test_none_token_preserves_order():
    jobs = [_job("a", score=0.3), _job("b", score=0.9)]
    assert [j.id for j in sort_jobs(jobs, None)] == ["a", "b"]


def test_unknown_token_preserves_order():
    jobs = [_job("a"), _job("b")]
    assert [j.id for j in sort_jobs(jobs, "bogus_desc")] == ["a", "b"]


def test_match_desc_and_asc():
    jobs = [_job("a", score=0.3), _job("b", score=0.9), _job("c", score=0.6)]
    assert [j.id for j in sort_jobs(jobs, "match_desc")] == ["b", "c", "a"]
    assert [j.id for j in sort_jobs(jobs, "match_asc")] == ["a", "c", "b"]


def test_match_nulls_last_regardless_of_direction():
    jobs = [_job("n1", score=None), _job("hi", score=0.9), _job("lo", score=0.1)]
    assert [j.id for j in sort_jobs(jobs, "match_desc")][-1] == "n1"
    assert [j.id for j in sort_jobs(jobs, "match_asc")][-1] == "n1"


def test_posted_desc_and_date_alias():
    jobs = [
        _job("old", date=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _job("new", date=datetime(2026, 5, 1, tzinfo=timezone.utc)),
    ]
    assert [j.id for j in sort_jobs(jobs, "posted_desc")] == ["new", "old"]
    assert [j.id for j in sort_jobs(jobs, "date_desc")] == ["new", "old"]
    assert [j.id for j in sort_jobs(jobs, "date_asc")] == ["old", "new"]


def test_posted_nulls_last():
    jobs = [_job("nd"), _job("d", date=datetime(2026, 5, 1, tzinfo=timezone.utc))]
    assert [j.id for j in sort_jobs(jobs, "posted_asc")] == ["d", "nd"]


def test_text_fields_case_insensitive_and_empty_last():
    jobs = [_job("z", title="zeta"), _job("a", title="Alpha"), _job("e", title="")]
    assert [j.id for j in sort_jobs(jobs, "title_asc")] == ["a", "z", "e"]


def test_company_and_source_sort():
    jobs = [_job("b", company="Beta", source="remotive"), _job("a", company="acme", source="jobicy")]
    assert [j.id for j in sort_jobs(jobs, "company_asc")] == ["a", "b"]
    # source_desc: "remotive" (b) > "jobicy" (a), so b comes first.
    assert [j.id for j in sort_jobs(jobs, "source_desc")] == ["b", "a"]

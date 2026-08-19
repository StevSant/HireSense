from __future__ import annotations

from types import SimpleNamespace

from hiresense.ingestion.domain import TRACKED_FIELDS, diff_job_fields


def _job(**overrides):
    base = {
        "title": "Engineer",
        "company": "Acme",
        "salary_range": None,
        "location": "Remote",
        "employment_type": "full_time",
        "description": "Build things.",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_identical_jobs_produce_an_empty_diff():
    assert diff_job_fields(_job(), _job()) == {}


def test_changed_scalar_field_records_old_and_new():
    diff = diff_job_fields(_job(), _job(title="Senior Engineer"))
    assert diff == {"title": {"old": "Engineer", "new": "Senior Engineer"}}


def test_none_to_value_is_a_change():
    diff = diff_job_fields(_job(), _job(salary_range="$180-200K"))
    assert diff == {"salary_range": {"old": None, "new": "$180-200K"}}


def test_description_reduces_to_a_boolean_flag():
    diff = diff_job_fields(_job(), _job(description="Build better things."))
    assert diff == {"description": {"changed": True}}


def test_untracked_field_change_produces_no_entry():
    old = _job()
    new = _job()
    old.match_score = 0.1
    new.match_score = 0.9
    assert diff_job_fields(old, new) == {}


def test_several_fields_change_at_once():
    diff = diff_job_fields(
        _job(), _job(title="Staff Engineer", location="Berlin", description="New.")
    )
    assert set(diff) == {"title", "location", "description"}


def test_description_is_not_in_tracked_fields():
    # description is diffed separately as a flag; TRACKED_FIELDS is the
    # before/after set only.
    assert "description" not in TRACKED_FIELDS
    assert "title" in TRACKED_FIELDS

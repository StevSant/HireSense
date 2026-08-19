from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.infrastructure import JobsRepository
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.shared.infrastructure.database import Base


def _repo():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return JobsRepository(session_factory=sessionmaker(bind=engine), bucket="boards")


def _job(**overrides) -> NormalizedJob:
    base = {
        "id": "job-1",
        "source": "remotive",
        "source_type": "feed",
        "source_id": "r-1",
        "title": "Engineer",
        "company": "Acme",
        "description": "Build things.",
        "url": "https://example.com/jobs/1",
        "location": "Remote",
    }
    base.update(overrides)
    return NormalizedJob(**base)


def test_insert_reports_no_changed_fields():
    repo = _repo()
    outcomes = repo.bulk_upsert([_job()])
    assert outcomes[0].result == UpsertResult.INSERTED
    assert outcomes[0].changed_fields == {}


def test_unchanged_reports_no_changed_fields():
    repo = _repo()
    repo.bulk_upsert([_job()])
    outcomes = repo.bulk_upsert([_job()])
    assert outcomes[0].result == UpsertResult.UNCHANGED
    assert outcomes[0].changed_fields == {}


def test_update_reports_the_fields_that_differed():
    repo = _repo()
    repo.bulk_upsert([_job()])
    outcomes = repo.bulk_upsert([_job(title="Senior Engineer", salary_range="$180-200K")])
    assert outcomes[0].result == UpsertResult.UPDATED
    assert outcomes[0].changed_fields == {
        "title": {"old": "Engineer", "new": "Senior Engineer"},
        "salary_range": {"old": None, "new": "$180-200K"},
    }


def test_reopen_without_content_change_reports_no_changed_fields():
    repo = _repo()
    outcomes = repo.bulk_upsert([_job()])
    repo.mark_closed([outcomes[0].job.id])
    reopened = repo.bulk_upsert([_job()])
    assert reopened[0].result == UpsertResult.REOPENED
    assert reopened[0].changed_fields == {}

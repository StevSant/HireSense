import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.infrastructure.database import Base
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.infrastructure.repository import TrackingRepository


@pytest.fixture
def sync_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    Base.metadata.drop_all(engine)


@pytest.fixture
def repo(sync_session_factory):
    return TrackingRepository(session_factory=sync_session_factory)


def test_create_and_get_by_id(repo) -> None:
    created = repo.create(
        TrackedApplication(title="SWE", company="Acme", status=ApplicationStatus.SAVED.value)
    )
    result = repo.get_by_id(created.id)
    assert result is not None
    assert result.title == "SWE"
    assert result.company == "Acme"


def test_get_by_id_not_found(repo) -> None:
    result = repo.get_by_id(uuid.uuid4())
    assert result is None


def test_get_by_job_id(repo) -> None:
    job_id = uuid.uuid4()
    repo.create(
        TrackedApplication(
            job_id=job_id, title="ML Eng", company="OpenAI", status=ApplicationStatus.SAVED.value
        )
    )
    result = repo.get_by_job_id(job_id)
    assert result is not None
    assert result.title == "ML Eng"


def test_get_by_job_id_not_found(repo) -> None:
    result = repo.get_by_job_id(uuid.uuid4())
    assert result is None


def test_list_all(repo) -> None:
    repo.create(TrackedApplication(title="A", company="X", status=ApplicationStatus.SAVED.value))
    repo.create(TrackedApplication(title="B", company="Y", status=ApplicationStatus.APPLIED.value))
    results = repo.list_all()
    assert len(results) == 2


def test_list_all_filter_by_status(repo) -> None:
    repo.create(TrackedApplication(title="A", company="X", status=ApplicationStatus.SAVED.value))
    repo.create(TrackedApplication(title="B", company="Y", status=ApplicationStatus.APPLIED.value))
    results = repo.list_all(status=ApplicationStatus.APPLIED)
    assert len(results) == 1
    assert results[0].title == "B"


def test_update(repo) -> None:
    created = repo.create(
        TrackedApplication(title="SWE", company="Acme", status=ApplicationStatus.SAVED.value)
    )
    updated = repo.get_by_id(created.id)
    updated.status = ApplicationStatus.APPLIED.value
    repo.save(updated)
    result = repo.get_by_id(created.id)
    assert result.status == ApplicationStatus.APPLIED.value


def test_manual_listing_metadata_round_trip_and_clear(repo) -> None:
    posted = datetime(2026, 7, 1, tzinfo=timezone.utc)
    created = repo.create(
        TrackedApplication(
            title="SWE",
            company="Acme",
            location="Quito",
            remote_modality="remote",
            salary_range="USD 1,500-2,000/mo",
            source="Referral",
            posted_date=posted,
        )
    )

    stored = repo.get_by_id(created.id)
    assert stored is not None
    assert stored.location == "Quito"
    assert stored.remote_modality == "remote"
    assert stored.salary_range == "USD 1,500-2,000/mo"
    assert stored.source == "Referral"
    # SQLite drops timezone metadata; PostgreSQL preserves it.
    assert stored.posted_date.replace(tzinfo=timezone.utc) == posted

    stored.location = None
    stored.salary_range = None
    repo.save(stored)

    cleared = repo.get_by_id(created.id)
    assert cleared is not None
    assert cleared.location is None
    assert cleared.salary_range is None


def test_delete(repo) -> None:
    created = repo.create(
        TrackedApplication(title="SWE", company="Acme", status=ApplicationStatus.SAVED.value)
    )
    deleted = repo.delete(created.id)
    assert deleted is True
    assert repo.get_by_id(created.id) is None


def test_delete_not_found(repo) -> None:
    deleted = repo.delete(uuid.uuid4())
    assert deleted is False

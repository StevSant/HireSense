import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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


def test_create_and_get_by_id(repo, sync_session_factory) -> None:
    app = TrackedApplication(title="SWE", company="Acme", status=ApplicationStatus.SAVED.value)
    with sync_session_factory() as session:
        session.add(app)
        session.commit()
        created_id = app.id
    result = repo.get_by_id(created_id)
    assert result is not None
    assert result.title == "SWE"
    assert result.company == "Acme"


def test_get_by_id_not_found(repo) -> None:
    result = repo.get_by_id(uuid.uuid4())
    assert result is None


def test_get_by_job_id(repo, sync_session_factory) -> None:
    job_id = uuid.uuid4()
    app = TrackedApplication(job_id=job_id, title="ML Eng", company="OpenAI", status=ApplicationStatus.SAVED.value)
    with sync_session_factory() as session:
        session.add(app)
        session.commit()
    result = repo.get_by_job_id(job_id)
    assert result is not None
    assert result.title == "ML Eng"


def test_get_by_job_id_not_found(repo) -> None:
    result = repo.get_by_job_id(uuid.uuid4())
    assert result is None


def test_list_all(repo, sync_session_factory) -> None:
    with sync_session_factory() as session:
        session.add(TrackedApplication(title="A", company="X", status=ApplicationStatus.SAVED.value))
        session.add(TrackedApplication(title="B", company="Y", status=ApplicationStatus.APPLIED.value))
        session.commit()
    results = repo.list_all()
    assert len(results) == 2


def test_list_all_filter_by_status(repo, sync_session_factory) -> None:
    with sync_session_factory() as session:
        session.add(TrackedApplication(title="A", company="X", status=ApplicationStatus.SAVED.value))
        session.add(TrackedApplication(title="B", company="Y", status=ApplicationStatus.APPLIED.value))
        session.commit()
    results = repo.list_all(status=ApplicationStatus.APPLIED)
    assert len(results) == 1
    assert results[0].title == "B"


def test_update(repo, sync_session_factory) -> None:
    app = TrackedApplication(title="SWE", company="Acme", status=ApplicationStatus.SAVED.value)
    with sync_session_factory() as session:
        session.add(app)
        session.commit()
        app_id = app.id
    updated = repo.get_by_id(app_id)
    updated.status = ApplicationStatus.APPLIED.value
    repo.save(updated)
    result = repo.get_by_id(app_id)
    assert result.status == ApplicationStatus.APPLIED.value


def test_delete(repo, sync_session_factory) -> None:
    app = TrackedApplication(title="SWE", company="Acme", status=ApplicationStatus.SAVED.value)
    with sync_session_factory() as session:
        session.add(app)
        session.commit()
        app_id = app.id
    deleted = repo.delete(app_id)
    assert deleted is True
    assert repo.get_by_id(app_id) is None


def test_delete_not_found(repo) -> None:
    deleted = repo.delete(uuid.uuid4())
    assert deleted is False

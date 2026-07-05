from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.scheduler.domain import JobRun, JobStatus
from hiresense.scheduler.infrastructure import (
    JobRunOrm,  # noqa: F401
    JobRunRepositoryImpl,
    JobToggleOrm,  # noqa: F401
    JobToggleRepositoryImpl,
)


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _run(name="autohunt_digest", status=JobStatus.SUCCESS, when=None):
    when = when or datetime.now(timezone.utc)
    return JobRun(
        job_name=name,
        started_at=when,
        finished_at=when,
        status=status,
        detail=None,
        items_affected=1,
        duration_seconds=0.0,
    )


def test_record_and_latest_and_recent():
    repo = JobRunRepositoryImpl(session_factory=_factory(), retention_days=30)
    repo.record(_run(status=JobStatus.SUCCESS))
    repo.record(_run(status=JobStatus.FAILURE))
    assert repo.latest("autohunt_digest").status is JobStatus.FAILURE
    assert len(repo.recent("autohunt_digest", limit=10)) == 2
    assert repo.latest("nonexistent") is None


def test_record_prunes_rows_older_than_retention():
    factory = _factory()
    repo = JobRunRepositoryImpl(session_factory=factory, retention_days=30)
    old = datetime.now(timezone.utc) - timedelta(days=40)
    repo.record(_run(when=old))
    repo.record(_run())  # recording prunes the 40-day-old row
    remaining = repo.recent("autohunt_digest", limit=10)
    assert len(remaining) == 1


def test_toggle_defaults_then_persists():
    repo = JobToggleRepositoryImpl(session_factory=_factory())
    # No row yet -> falls back to the supplied default.
    assert repo.is_enabled("autohunt_digest", default=True) is True
    repo.set_enabled("autohunt_digest", False)
    assert repo.is_enabled("autohunt_digest", default=True) is False
    assert repo.all_states() == {"autohunt_digest": False}

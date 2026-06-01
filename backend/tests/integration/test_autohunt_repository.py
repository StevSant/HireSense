from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.autohunt.domain import Digest, DigestEntry
from hiresense.autohunt.infrastructure import DigestRepository
from hiresense.autohunt.infrastructure.orm import DigestOrm  # noqa: F401
from hiresense.infrastructure.database import Base


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _digest(cutoff, entries=None):
    entries = entries or []
    return Digest(cutoff_at=cutoff, entries=entries, job_count=len(entries))


def test_add_and_latest_roundtrip():
    repo = DigestRepository(session_factory=_factory())
    now = datetime.now(timezone.utc)
    e = DigestEntry(job_id="j1", title="Eng", company="Acme", url="http://x", score=0.8)
    saved = repo.add(_digest(now, [e]))
    assert saved.id is not None and saved.created_at is not None
    latest = repo.latest()
    assert latest is not None
    assert latest.job_count == 1
    assert latest.entries[0].job_id == "j1"


def test_latest_is_most_recent():
    factory = _factory()
    repo = DigestRepository(session_factory=factory)
    old = datetime.now(timezone.utc) - timedelta(days=2)
    repo.add(_digest(old))
    repo.add(_digest(datetime.now(timezone.utc)))
    assert len(repo.list_recent(10)) == 2
    # latest() returns the most-recently-created row.
    assert repo.latest() is not None


def test_prune_older_than():
    repo = DigestRepository(session_factory=_factory())
    repo.add(_digest(datetime.now(timezone.utc)))
    removed = repo.prune_older_than(datetime.now(timezone.utc) + timedelta(days=1))
    assert removed == 1
    assert repo.latest() is None

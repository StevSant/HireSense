import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.inbox.domain import DetectedSignal, EmailSignalKind, SignalState
from hiresense.inbox.infrastructure import DetectedSignalOrm, DetectedSignalRepositoryImpl  # noqa: F401


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _signal(mid="m1"):
    return DetectedSignal(
        message_id=mid,
        from_address="r@acme.com",
        subject="App",
        received_at=datetime.now(timezone.utc),
        kind=EmailSignalKind.REJECTION,
        company="Acme",
        role="Dev",
        confidence=0.9,
        matched_application_id=uuid.uuid4(),
        proposed_status="rejected",
    )


def test_add_list_get_setstate_dedup():
    repo = DetectedSignalRepositoryImpl(session_factory=_factory())
    added = repo.add(_signal())
    assert added.id is not None
    assert repo.exists_message_id("m1") is True
    assert repo.exists_message_id("nope") is False
    assert len(repo.list()) == 1
    assert len(repo.list(state=SignalState.PENDING)) == 1
    assert len(repo.list(state=SignalState.APPLIED)) == 0
    updated = repo.set_state(added.id, SignalState.APPLIED)
    assert updated.state is SignalState.APPLIED
    assert repo.get(added.id).state is SignalState.APPLIED


def test_add_duplicate_message_id_is_skipped_not_raised():
    """A concurrent insert that loses the unique-constraint race must be
    skipped (returns None), not raise IntegrityError (issue #150)."""
    repo = DetectedSignalRepositoryImpl(session_factory=_factory())
    first = repo.add(_signal("dup"))
    assert first is not None
    # Second insert with the same message_id returns None rather than raising.
    assert repo.add(_signal("dup")) is None
    assert len(repo.list()) == 1

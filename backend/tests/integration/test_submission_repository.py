import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.shared.infrastructure import registry  # noqa: F401  (populates metadata)
from hiresense.shared.infrastructure.database import Base
from hiresense.submission.domain import (
    SubmissionAttempt,
    SubmissionEvent,
    SubmissionEventKind,
    SubmissionStatus,
)
from hiresense.submission.infrastructure import SubmissionRepositoryImpl


@pytest.fixture()
def repo():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return SubmissionRepositoryImpl(session_factory=sessionmaker(bind=engine))


def _attempt(**kw):
    base = dict(
        application_id=uuid.uuid4(),
        job_id="j1",
        channel="ats_form",
        target_url="https://x.test/apply",
    )
    base.update(kw)
    return SubmissionAttempt(**base)


def test_lease_claims_each_attempt_at_most_once(repo):
    repo.create(_attempt())
    repo.create(_attempt())
    now = datetime.now(timezone.utc)
    first = repo.lease("runner-a", capacity=1, lease_seconds=300, now=now)
    second = repo.lease("runner-b", capacity=5, lease_seconds=300, now=now)
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id != second[0].id
    assert first[0].status is SubmissionStatus.CLAIMED
    assert first[0].runner_id == "runner-a"
    assert repo.lease("runner-c", capacity=5, lease_seconds=300, now=now) == []


def test_lease_with_no_capacity_claims_nothing(repo):
    repo.create(_attempt())
    assert repo.lease("r", capacity=0, lease_seconds=300, now=datetime.now(timezone.utc)) == []


def test_expired_lease_requeues_until_max_attempts(repo):
    created = repo.create(_attempt())
    now = datetime.now(timezone.utc)
    repo.lease("runner-a", capacity=1, lease_seconds=60, now=now)
    later = now + timedelta(seconds=120)

    assert repo.expire_leases(later, max_attempts=2) == 1
    requeued = repo.get(created.id)
    assert requeued.status is SubmissionStatus.QUEUED
    assert requeued.attempt_no == 2

    repo.lease("runner-a", capacity=1, lease_seconds=60, now=later)
    assert repo.expire_leases(later + timedelta(seconds=120), max_attempts=2) == 1
    exhausted = repo.get(created.id)
    assert exhausted.status is SubmissionStatus.FAILED
    assert exhausted.finished_at is not None


def test_live_lease_is_not_expired(repo):
    repo.create(_attempt())
    now = datetime.now(timezone.utc)
    repo.lease("runner-a", capacity=1, lease_seconds=300, now=now)
    assert repo.expire_leases(now + timedelta(seconds=10), max_attempts=2) == 0


def test_has_live_attempt_ignores_terminal_rows(repo):
    app_id = uuid.uuid4()
    created = repo.create(_attempt(application_id=app_id))
    assert repo.has_live_attempt(app_id) is True
    repo.update(created.model_copy(update={"status": SubmissionStatus.SUBMITTED}))
    assert repo.has_live_attempt(app_id) is False


def test_count_created_since_windows_correctly(repo):
    repo.create(_attempt())
    now = datetime.now(timezone.utc)
    assert repo.count_created_since(now - timedelta(hours=1)) == 1
    assert repo.count_created_since(now + timedelta(hours=1)) == 0


def test_list_filters_by_status(repo):
    escalated = repo.create(_attempt())
    repo.create(_attempt())
    repo.update(escalated.model_copy(update={"status": SubmissionStatus.ESCALATED}))
    rows = repo.list(status=SubmissionStatus.ESCALATED, limit=10)
    assert [r.id for r in rows] == [escalated.id]


def test_events_are_ordered_by_seq(repo):
    created = repo.create(_attempt())
    for seq, kind in enumerate([SubmissionEventKind.NAVIGATE, SubmissionEventKind.FILL]):
        repo.append_event(
            SubmissionEvent(attempt_id=created.id, seq=seq, kind=kind, payload={"i": seq})
        )
    assert [e.seq for e in repo.events(created.id)] == [0, 1]


def test_next_seq_starts_at_zero_and_increments(repo):
    created = repo.create(_attempt())
    assert repo.next_seq(created.id) == 0
    repo.append_event(
        SubmissionEvent(attempt_id=created.id, seq=0, kind=SubmissionEventKind.NAVIGATE)
    )
    assert repo.next_seq(created.id) == 1


def test_escalation_fields_round_trip(repo):
    created = repo.create(_attempt())
    updated = repo.update(
        created.model_copy(
            update={
                "status": SubmissionStatus.ESCALATED,
                "escalated_fields": ["#salary", "#start"],
                "escalation_reason": "Needs a human answer",
            }
        )
    )
    assert updated.escalated_fields == ["#salary", "#start"]
    assert repo.get(created.id).escalation_reason == "Needs a human answer"

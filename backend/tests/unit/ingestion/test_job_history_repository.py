from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.ingestion.domain import JobClosureReason, JobHistoryEvent, JobHistoryEventType
from hiresense.ingestion.infrastructure import JobHistoryRepository
from hiresense.shared.infrastructure.database import Base

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _repo():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return JobHistoryRepository(session_factory=sessionmaker(bind=engine))


def _event(job_id: str, event: JobHistoryEventType, *, at: datetime = NOW, **kwargs):
    return JobHistoryEvent(job_id=job_id, event=event, occurred_at=at, **kwargs)


def test_start_run_then_finish_run_updates_status_and_finished_at():
    repo = _repo()
    run_id = repo.start_run("fetch", NOW)
    assert repo.get_run(run_id).status == "running"
    assert repo.get_run(run_id).finished_at is None

    repo.finish_run(run_id, "completed", NOW + timedelta(minutes=3))
    summary = repo.get_run(run_id)
    assert summary.status == "completed"
    assert summary.finished_at is not None


def test_insert_events_and_read_them_back_for_a_job_newest_first():
    repo = _repo()
    run_id = repo.start_run("fetch", NOW)
    repo.insert_events(
        run_id,
        [
            _event("job-1", JobHistoryEventType.INSERTED, at=NOW),
            _event("job-1", JobHistoryEventType.UPDATED, at=NOW + timedelta(days=1)),
            _event("job-2", JobHistoryEventType.INSERTED, at=NOW),
        ],
    )
    events = repo.list_events_for_job("job-1", limit=10)
    assert [e.event for e in events] == [
        JobHistoryEventType.UPDATED,
        JobHistoryEventType.INSERTED,
    ]


def test_run_summary_counts_are_aggregated_per_event_type():
    repo = _repo()
    run_id = repo.start_run("scheduler", NOW)
    repo.insert_events(
        run_id,
        [
            _event("a", JobHistoryEventType.INSERTED),
            _event("b", JobHistoryEventType.INSERTED),
            _event("c", JobHistoryEventType.UPDATED),
            _event("d", JobHistoryEventType.REOPENED),
        ],
    )
    summary = repo.get_run(run_id)
    assert (summary.inserted, summary.updated, summary.reopened, summary.closed) == (2, 1, 1, 0)


def test_events_with_no_run_are_stored_and_keep_their_reason():
    repo = _repo()
    repo.insert_events(
        None,
        [
            _event(
                "job-9",
                JobHistoryEventType.CLOSED,
                reason=JobClosureReason.DEAD_END_REDIRECT,
            )
        ],
    )
    event = repo.list_events_for_job("job-9", limit=10)[0]
    assert event.reason == JobClosureReason.DEAD_END_REDIRECT


def test_insert_events_with_an_empty_list_is_a_no_op():
    repo = _repo()
    repo.insert_events(None, [])
    assert repo.list_events_for_job("job-1", limit=10) == []


def test_list_runs_returns_newest_first_with_counts():
    repo = _repo()
    old_run = repo.start_run("fetch", NOW - timedelta(days=1))
    new_run = repo.start_run("scheduler", NOW)
    repo.insert_events(new_run, [_event("a", JobHistoryEventType.INSERTED)])

    runs = repo.list_runs(limit=10, offset=0)
    assert [r.id for r in runs] == [new_run, old_run]
    assert runs[0].inserted == 1
    assert runs[1].inserted == 0


def test_prune_removes_events_past_the_cutoff_and_keeps_recent_ones():
    repo = _repo()
    repo.insert_events(
        None,
        [
            _event("old", JobHistoryEventType.CLOSED, at=NOW - timedelta(days=200)),
            _event("new", JobHistoryEventType.CLOSED, at=NOW),
        ],
    )
    deleted = repo.prune_events_older_than(NOW - timedelta(days=90))
    assert deleted == 1
    assert repo.list_events_for_job("old", limit=10) == []
    assert len(repo.list_events_for_job("new", limit=10)) == 1

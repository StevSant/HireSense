from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain import (
    JobClosureReason,
    JobHistoryEventType,
    JobHistoryRecorder,
)
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.ports.jobs_repository import UpsertOutcome

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


class FakeStore:
    def __init__(self) -> None:
        self.runs: list[tuple[str, datetime]] = []
        self.finished: list[tuple[str, str]] = []
        self.batches: list[tuple[str | None, list]] = []
        self.pruned: list[datetime] = []

    def start_run(self, trigger, started_at):
        self.runs.append((trigger, started_at))
        return "run-1"

    def finish_run(self, run_id, status, finished_at):
        self.finished.append((run_id, status))

    def insert_events(self, run_id, events):
        self.batches.append((run_id, events))

    def prune_events_older_than(self, cutoff):
        self.pruned.append(cutoff)
        return 0


class ExplodingStore(FakeStore):
    def start_run(self, trigger, started_at):
        raise RuntimeError("db down")

    def insert_events(self, run_id, events):
        raise RuntimeError("db down")


def _job(job_id: str) -> NormalizedJob:
    return NormalizedJob(
        id=job_id,
        source="remotive",
        source_type="feed",
        source_id=job_id,
        title="Engineer",
        company="Acme",
        description="Build things.",
        url=f"https://example.com/{job_id}",
    )


def _recorder(store):
    return JobHistoryRecorder(store=store, clock=lambda: NOW)


def test_unchanged_outcomes_are_skipped():
    store = FakeStore()
    _recorder(store).record_outcomes(
        "run-1",
        [
            UpsertOutcome(job=_job("a"), result=UpsertResult.UNCHANGED),
            UpsertOutcome(job=_job("b"), result=UpsertResult.INSERTED),
        ],
    )
    (_, events) = store.batches[0]
    assert [e.job_id for e in events] == ["b"]


def test_all_outcomes_unchanged_writes_nothing_at_all():
    store = FakeStore()
    _recorder(store).record_outcomes(
        "run-1", [UpsertOutcome(job=_job("a"), result=UpsertResult.UNCHANGED)]
    )
    assert store.batches == []


def test_outcomes_are_written_in_one_batch_carrying_the_diff():
    store = FakeStore()
    _recorder(store).record_outcomes(
        "run-1",
        [
            UpsertOutcome(job=_job("a"), result=UpsertResult.INSERTED),
            UpsertOutcome(
                job=_job("b"),
                result=UpsertResult.UPDATED,
                changed_fields={"title": {"old": "x", "new": "y"}},
            ),
            UpsertOutcome(job=_job("c"), result=UpsertResult.REOPENED),
        ],
    )
    assert len(store.batches) == 1
    run_id, events = store.batches[0]
    assert run_id == "run-1"
    assert [e.event for e in events] == [
        JobHistoryEventType.INSERTED,
        JobHistoryEventType.UPDATED,
        JobHistoryEventType.REOPENED,
    ]
    assert events[1].changed_fields == {"title": {"old": "x", "new": "y"}}
    assert all(e.occurred_at == NOW for e in events)


def test_closures_carry_their_reason_and_no_run_by_default():
    store = FakeStore()
    _recorder(store).record_closures(["a", "b"], JobClosureReason.PROBE_404)
    run_id, events = store.batches[0]
    assert run_id is None
    assert [e.event for e in events] == [JobHistoryEventType.CLOSED] * 2
    assert all(e.reason == JobClosureReason.PROBE_404 for e in events)


def test_closures_can_be_attributed_to_a_run():
    store = FakeStore()
    _recorder(store).record_closures(["a"], JobClosureReason.SNAPSHOT_DISAPPEARANCE, run_id="run-1")
    assert store.batches[0][0] == "run-1"


def test_empty_closure_list_writes_nothing():
    store = FakeStore()
    _recorder(store).record_closures([], JobClosureReason.EXPIRY)
    assert store.batches == []


def test_a_failing_store_is_swallowed_and_never_raises():
    recorder = _recorder(ExplodingStore())
    assert recorder.start_run("fetch") is None
    recorder.record_outcomes("run-1", [UpsertOutcome(job=_job("a"), result=UpsertResult.INSERTED)])
    recorder.record_closures(["a"], JobClosureReason.EXPIRY)


def test_start_and_finish_run_pass_through_the_clock():
    store = FakeStore()
    recorder = _recorder(store)
    run_id = recorder.start_run("scheduler")
    recorder.finish_run(run_id, "completed")
    assert store.runs == [("scheduler", NOW)]
    assert store.finished == [("run-1", "completed")]


def test_finish_run_with_no_run_id_is_a_no_op():
    store = FakeStore()
    _recorder(store).finish_run(None, "failed")
    assert store.finished == []

from datetime import datetime, timezone

import pytest

from hiresense.ingestion.domain.job_closure_reason import JobClosureReason
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.ingestion.infrastructure import InMemoryJobsRepository
from hiresense.shared.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.shared.kernel.value_objects import SourceType


class FakeJobSource:
    def source_name(self) -> str:
        return "fake"

    def source_type(self) -> SourceType:
        return SourceType.API

    def supports_snapshot_closure(self) -> bool:
        return False

    async def fetch_jobs(self, filters=None) -> list[RawJobListing]:
        return [
            RawJobListing(
                source="fake",
                source_id="1",
                raw_data={
                    "title": "Engineer",
                    "company_name": "Co",
                    "description": "Do stuff",
                    "tags": ["python"],
                    "candidate_required_location": "Remote",
                    "salary": "",
                    "url": "https://example.com/1",
                    "publication_date": "2026-03-28T12:00:00",
                },
            )
        ]


class FakeNormalizer:
    def normalize(self, raw: RawJobListing) -> dict:
        return {
            "title": raw.raw_data["title"],
            "company": raw.raw_data.get("company_name", ""),
            "description": raw.raw_data.get("description", ""),
            "skills": raw.raw_data.get("tags", []),
            "location": raw.raw_data.get("candidate_required_location", ""),
            "salary_range": raw.raw_data.get("salary") or None,
            "url": raw.raw_data.get("url", ""),
            "language": "en",
        }


def _raw(sid: str, *, title: str = "Engineer", salary: str = "") -> RawJobListing:
    return RawJobListing(
        source="snap",
        source_id=sid,
        raw_data={
            "title": title,
            "company_name": "Co",
            "description": "Do stuff",
            "tags": ["python"],
            "candidate_required_location": "Remote",
            "salary": salary,
            "url": f"https://example.com/{sid}",
            "publication_date": "2026-03-28T12:00:00",
        },
    )


class ScriptedSource:
    """Returns a pre-scripted list of RawJobListing per successive run()."""

    def __init__(self, runs: list[list[RawJobListing]], *, snapshot: bool) -> None:
        self._runs = runs
        self._snapshot = snapshot
        self._i = 0

    def source_name(self) -> str:
        return "snap"

    def source_type(self) -> SourceType:
        return SourceType.API

    def supports_snapshot_closure(self) -> bool:
        return self._snapshot

    async def fetch_jobs(self, filters=None) -> list[RawJobListing]:
        batch = self._runs[min(self._i, len(self._runs) - 1)]
        self._i += 1
        return batch


class _BoomRepository(InMemoryJobsRepository):
    """Fails the upsert step on every run, so a pass never completes."""

    def bulk_upsert(self, jobs):
        raise RuntimeError("db down")


class FakeRecorder:
    """Captures calls, modelled on Task 6's FakeStore."""

    def __init__(self) -> None:
        self.started: list[str] = []
        self.finished: list[tuple[str | None, str]] = []
        self.outcomes: list[tuple[str | None, list]] = []
        self.closures: list[tuple[list[str], JobClosureReason, str | None]] = []
        self.pruned: list[datetime] = []
        self._next_run_id = 0

    def start_run(self, trigger: str) -> str | None:
        self._next_run_id += 1
        run_id = f"run-{self._next_run_id}"
        self.started.append(trigger)
        return run_id

    def finish_run(self, run_id, status: str) -> None:
        self.finished.append((run_id, status))

    def record_outcomes(self, run_id, outcomes) -> None:
        self.outcomes.append((run_id, list(outcomes)))

    def record_closures(self, job_ids, reason, run_id=None) -> None:
        self.closures.append((list(job_ids), reason, run_id))

    def prune(self, cutoff: datetime) -> None:
        self.pruned.append(cutoff)


def _orch(source, history=None, **kw):
    return IngestionOrchestrator(
        sources=[source],
        normalizers={source.source_name(): FakeNormalizer()},
        event_bus=InMemoryEventBus(),
        repository=InMemoryJobsRepository(),
        cooldown_seconds=0,
        history=history,
        **kw,
    )


@pytest.mark.asyncio
async def test_run_opens_and_completes_a_run() -> None:
    recorder = FakeRecorder()
    orch = _orch(FakeJobSource(), history=recorder)

    await orch.run()

    assert recorder.started == ["fetch"]
    assert len(recorder.finished) == 1
    run_id, status = recorder.finished[0]
    assert run_id == "run-1"
    assert status == "completed"


@pytest.mark.asyncio
async def test_a_crashed_pass_marks_the_run_failed() -> None:
    recorder = FakeRecorder()
    orch = IngestionOrchestrator(
        sources=[FakeJobSource()],
        normalizers={"fake": FakeNormalizer()},
        event_bus=InMemoryEventBus(),
        repository=_BoomRepository(),
        cooldown_seconds=0,
        history=recorder,
    )

    with pytest.raises(RuntimeError):
        await orch.run()

    assert len(recorder.finished) == 1
    run_id, status = recorder.finished[0]
    assert run_id == "run-1"
    assert status == "failed"


@pytest.mark.asyncio
async def test_outcomes_are_recorded_with_the_run_id() -> None:
    recorder = FakeRecorder()
    orch = _orch(FakeJobSource(), history=recorder)

    await orch.run()

    assert len(recorder.outcomes) == 1
    run_id, outcomes = recorder.outcomes[0]
    assert run_id == "run-1"
    assert len(outcomes) == 1


@pytest.mark.asyncio
async def test_snapshot_closures_are_recorded_with_the_disappearance_reason() -> None:
    recorder = FakeRecorder()
    source = ScriptedSource([[_raw("1"), _raw("2")], [_raw("1")], [_raw("1")]], snapshot=True)
    orch = _orch(source, history=recorder, closure_miss_threshold=2)

    await orch.run()  # run 1: A, B inserted
    await orch.run()  # run 2: B missed once
    await orch.run()  # run 3: B missed twice -> closed

    assert len(recorder.closures) == 1
    job_ids, reason, run_id = recorder.closures[0]
    assert len(job_ids) == 1
    assert reason == JobClosureReason.SNAPSHOT_DISAPPEARANCE
    assert run_id == "run-3"


@pytest.mark.asyncio
async def test_scheduler_trigger_is_passed_through() -> None:
    recorder = FakeRecorder()
    orch = _orch(FakeJobSource(), history=recorder)

    await orch.run(trigger="scheduler")

    assert recorder.started == ["scheduler"]


@pytest.mark.asyncio
async def test_orchestrator_without_a_recorder_still_runs() -> None:
    orch = _orch(FakeJobSource(), history=None)

    result = await orch.run()

    assert len(result) == 1
    assert result[0].title == "Engineer"


@pytest.mark.asyncio
async def test_history_is_pruned_with_its_own_retention_window() -> None:
    recorder = FakeRecorder()
    orch = IngestionOrchestrator(
        sources=[],
        normalizers={},
        event_bus=InMemoryEventBus(),
        repository=InMemoryJobsRepository(),
        cooldown_seconds=0,
        history=recorder,
        history_retention_days=30,
        retention_days=None,  # job pruning disabled, history pruning must still run
    )

    await orch._prune_expired()

    assert len(recorder.pruned) == 1
    cutoff = recorder.pruned[0]
    delta = datetime.now(timezone.utc) - cutoff
    assert 29 <= delta.days <= 30

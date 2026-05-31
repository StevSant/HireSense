import asyncio

import pytest

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.ingestion.infrastructure import InMemoryJobsRepository
from hiresense.kernel.events import DomainEvent
from hiresense.kernel.value_objects import SourceType


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


@pytest.mark.asyncio
async def test_orchestrator_fetches_and_publishes() -> None:
    bus = InMemoryEventBus()
    events: list[DomainEvent] = []

    async def capture(event: DomainEvent) -> None:
        events.append(event)

    bus.subscribe("jobs.ingested", capture)

    normalizers = {"fake": FakeNormalizer()}
    orchestrator = IngestionOrchestrator(
        sources=[FakeJobSource()],
        normalizers=normalizers,
        event_bus=bus,
        repository=InMemoryJobsRepository(),
    )
    result = await orchestrator.run()
    assert len(result) == 1
    assert result[0].title == "Engineer"

    await asyncio.sleep(0.05)
    assert len(events) == 1
    assert events[0].event_type == "jobs.ingested"


# --- Lifecycle: change detection + disappearance closure (Task 11) ---

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


class FakeIndexer:
    def __init__(self) -> None:
        self.indexed: list[list[str]] = []
        self.removed: list[list[str]] = []

    async def index(self, jobs) -> int:
        self.indexed.append([j.id for j in jobs])
        return len(jobs)

    async def remove(self, job_ids) -> None:
        self.removed.append(list(job_ids))


def _orch(source, indexer, **kw):
    return IngestionOrchestrator(
        sources=[source],
        normalizers={"snap": FakeNormalizer()},
        event_bus=InMemoryEventBus(),
        repository=InMemoryJobsRepository(),
        cooldown_seconds=0,  # allow repeated run() in-test
        indexer=indexer,
        **kw,
    )


@pytest.mark.asyncio
async def test_closes_job_missing_from_snapshot_source_after_threshold() -> None:
    source = ScriptedSource(
        [[_raw("1"), _raw("2")], [_raw("1")], [_raw("1")]], snapshot=True
    )
    indexer = FakeIndexer()
    orch = _orch(source, indexer)  # default threshold 2

    await orch.run()  # run 1: A, B inserted
    repo = orch._repository
    b_id = next(j.id for j in repo.list_all() if j.source_id == "2")
    assert all(j.status == "open" for j in repo.list_all())

    await orch.run()  # run 2: B missed -> missed_count 1, still open
    assert repo.get_by_id(b_id).status == "open"

    await orch.run()  # run 3: B missed -> missed_count 2 -> closed
    assert repo.get_by_id(b_id).status == "closed"
    assert indexer.removed[-1] == [b_id]


@pytest.mark.asyncio
async def test_non_snapshot_source_never_closes() -> None:
    source = ScriptedSource(
        [[_raw("1"), _raw("2")], [_raw("1")], [_raw("1")], [_raw("1")]], snapshot=False
    )
    indexer = FakeIndexer()
    orch = _orch(source, indexer)

    for _ in range(4):
        await orch.run()

    assert all(j.status == "open" for j in orch._repository.list_all())
    assert indexer.removed == []  # disappearance never runs for non-snapshot sources


@pytest.mark.asyncio
async def test_changed_job_is_reindexed_with_same_id() -> None:
    source = ScriptedSource(
        [[_raw("1", salary="")], [_raw("1", salary="$200k")]], snapshot=True
    )
    indexer = FakeIndexer()
    orch = _orch(source, indexer)

    await orch.run()  # insert
    repo = orch._repository
    job_id = repo.list_all()[0].id
    indexer.indexed.clear()

    await orch.run()  # salary changed -> UPDATED -> re-indexed, same id
    assert indexer.indexed[-1] == [job_id]
    stored = repo.list_all()
    assert len(stored) == 1 and stored[0].id == job_id
    assert stored[0].salary_range == "$200k"

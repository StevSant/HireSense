"""The portals bucket records the same audit trail as the boards bucket.

Mirrors `test_orchestrator_history.py`: a `PortalScanner` driven by scripted
adapters against a `FakeRecorder`, asserting the run header, the outcomes, the
snapshot-disappearance closures, and that no recorder at all still scans.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from hiresense.ingestion.domain.job_closure_reason import JobClosureReason
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner, ScanFilters
from hiresense.ingestion.infrastructure import InMemoryJobsRepository
from hiresense.shared.kernel.events import DomainEvent


class FakeNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        return {
            "title": raw.raw_data.get("title", "Engineer"),
            "company": "Acme",
            "description": "Some description",
            "skills": [],
            "location": "Remote",
            "salary_range": None,
            "url": raw.raw_data.get("url", "https://example.com/1"),
            "language": "en",
            "posted_date": None,
        }


class FakeEventBus:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.published.append(event)


class ScriptedAdapter:
    """Returns a pre-scripted batch per successive scan()."""

    def __init__(self, batches: list[list[RawJobListing]], *, snapshot: bool = True) -> None:
        self._batches = batches
        self._snapshot = snapshot
        self._i = 0

    def supports_snapshot_closure(self) -> bool:
        return self._snapshot

    async def fetch_jobs(self, board_id: str, company_name: str) -> list[RawJobListing]:
        batch = self._batches[min(self._i, len(self._batches) - 1)]
        self._i += 1
        return batch


class BoomRepository(InMemoryJobsRepository):
    """Fails the upsert step, so a scan never completes."""

    def bulk_upsert(self, jobs):
        raise RuntimeError("db down")


class FakeRecorder:
    """Captures calls, modelled on the orchestrator's history test."""

    def __init__(self, *, run_id: str | None = "run-1") -> None:
        self.started: list[str] = []
        self.finished: list[tuple[str | None, str]] = []
        self.outcomes: list[tuple[str | None, list]] = []
        self.closures: list[tuple[list[str], JobClosureReason, str | None]] = []
        self.pruned: list[datetime] = []
        self._run_id = run_id

    def start_run(self, trigger: str) -> str | None:
        self.started.append(trigger)
        return self._run_id

    def finish_run(self, run_id, status: str) -> None:
        self.finished.append((run_id, status))

    def record_outcomes(self, run_id, outcomes) -> None:
        self.outcomes.append((run_id, list(outcomes)))

    def record_closures(self, job_ids, reason, run_id=None) -> None:
        self.closures.append((list(job_ids), reason, run_id))

    def prune(self, cutoff: datetime) -> None:
        self.pruned.append(cutoff)


def _raw(sid: str, *, title: str = "Engineer") -> RawJobListing:
    return RawJobListing(
        source="AcmeCo",
        source_id=sid,
        raw_data={"title": title, "url": f"https://example.com/{sid}"},
    )


def _scanner(adapter, history=None, repository=None, **kw) -> PortalScanner:
    return PortalScanner(
        config=PortalsConfig(
            portals=[
                PortalEntry(
                    name="AcmeCo",
                    platform="greenhouse",
                    board_id="acme",
                    categories=["engineering"],
                )
            ]
        ),
        adapters={"greenhouse": adapter},
        normalizers={"greenhouse": FakeNormalizer()},
        event_bus=FakeEventBus(),
        repository=repository or InMemoryJobsRepository(),
        history=history,
        **kw,
    )


@pytest.mark.asyncio
async def test_a_scan_opens_and_completes_a_run() -> None:
    recorder = FakeRecorder()
    scanner = _scanner(ScriptedAdapter([[_raw("1")]]), history=recorder)

    await scanner.scan(ScanFilters())

    assert recorder.started == ["portal_scan"]
    assert recorder.finished == [("run-1", "completed")]


@pytest.mark.asyncio
async def test_the_trigger_distinguishes_a_portal_scan_from_a_board_fetch() -> None:
    recorder = FakeRecorder()
    scanner = _scanner(ScriptedAdapter([[_raw("1")]]), history=recorder)

    await scanner.scan(ScanFilters())

    assert recorder.started == ["portal_scan"]


@pytest.mark.asyncio
async def test_a_crashed_scan_marks_the_run_failed() -> None:
    recorder = FakeRecorder()
    scanner = _scanner(
        ScriptedAdapter([[_raw("1")]]), history=recorder, repository=BoomRepository()
    )

    with pytest.raises(RuntimeError):
        await scanner.scan(ScanFilters())

    assert recorder.finished == [("run-1", "failed")]


@pytest.mark.asyncio
async def test_outcomes_are_recorded_with_the_run_id() -> None:
    recorder = FakeRecorder()
    scanner = _scanner(ScriptedAdapter([[_raw("1"), _raw("2")]]), history=recorder)

    await scanner.scan(ScanFilters())

    assert len(recorder.outcomes) == 1
    run_id, outcomes = recorder.outcomes[0]
    assert run_id == "run-1"
    assert len(outcomes) == 2


@pytest.mark.asyncio
async def test_snapshot_closures_are_recorded_with_the_disappearance_reason() -> None:
    recorder = FakeRecorder()
    adapter = ScriptedAdapter([[_raw("1"), _raw("2")], [_raw("1")], [_raw("1")]])
    scanner = _scanner(adapter, history=recorder, closure_miss_threshold=2)

    await scanner.scan(ScanFilters())  # 1, 2 inserted
    await scanner.scan(ScanFilters())  # 2 missed once
    await scanner.scan(ScanFilters())  # 2 missed twice -> closed

    assert len(recorder.closures) == 1
    job_ids, reason, run_id = recorder.closures[0]
    assert len(job_ids) == 1
    assert reason == JobClosureReason.SNAPSHOT_DISAPPEARANCE
    assert run_id == "run-1"


@pytest.mark.asyncio
async def test_history_is_pruned_with_its_own_retention_window() -> None:
    recorder = FakeRecorder()
    scanner = _scanner(
        ScriptedAdapter([[]]),
        history=recorder,
        retention_days=None,  # job pruning disabled, history pruning must still run
        history_retention_days=30,
    )

    await scanner.scan(ScanFilters())

    assert len(recorder.pruned) == 1
    delta = datetime.now(timezone.utc) - recorder.pruned[0]
    assert 29 <= delta.days <= 30


@pytest.mark.asyncio
async def test_a_scan_without_a_recorder_still_works() -> None:
    scanner = _scanner(ScriptedAdapter([[_raw("1")]]), history=None)

    result = await scanner.scan(ScanFilters())

    assert result.new == 1


@pytest.mark.asyncio
async def test_a_failed_run_header_still_records_events_without_a_run_id() -> None:
    recorder = FakeRecorder(run_id=None)
    scanner = _scanner(ScriptedAdapter([[_raw("1")]]), history=recorder)

    await scanner.scan(ScanFilters())

    assert recorder.finished == []
    assert recorder.outcomes[0][0] is None

from __future__ import annotations

from typing import Any

import pytest

from hiresense.ingestion.domain.models import NormalizedJob, RawJobListing
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.domain.portal_scanner import (
    PortalScanner,
    ScanFilters,
    ScanResult,
)
from hiresense.kernel.events import DomainEvent


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeAdapter:
    def __init__(self, jobs: list[RawJobListing] | None = None, *, raise_on_fetch: bool = False) -> None:
        self._jobs = jobs or []
        self._raise_on_fetch = raise_on_fetch
        self.calls: list[tuple[str, str]] = []

    async def fetch_jobs(self, board_id: str, company_name: str) -> list[RawJobListing]:
        self.calls.append((board_id, company_name))
        if self._raise_on_fetch:
            raise RuntimeError("network error")
        return self._jobs


class FakeNormalizer:
    def __init__(self, title: str = "Engineer", company: str = "Acme", url: str = "https://example.com/1") -> None:
        self._title = title
        self._company = company
        self._url = url

    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        return {
            "title": raw.raw_data.get("title", self._title),
            "company": raw.raw_data.get("company", self._company),
            "description": "Some description",
            "skills": [],
            "location": "Remote",
            "salary_range": None,
            "url": raw.raw_data.get("url", self._url),
            "language": "en",
            "posted_date": None,
        }


class FakeEventBus:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.published.append(event)


def _make_raw(title: str = "Engineer", company: str = "Acme", url: str = "https://example.com/1") -> RawJobListing:
    return RawJobListing(
        source="test",
        source_id="1",
        raw_data={"title": title, "company": company, "url": url},
    )


def _make_config(*portals: PortalEntry) -> PortalsConfig:
    return PortalsConfig(portals=list(portals))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_all_portals() -> None:
    """Two portals on different platforms — both get scanned and results merged."""
    raw_gh = _make_raw("Backend Dev", "GreenCo", "https://gh.example.com/1")
    raw_lv = _make_raw("Frontend Dev", "LeverCo", "https://lv.example.com/1")

    adapter_gh = FakeAdapter([raw_gh])
    adapter_lv = FakeAdapter([raw_lv])

    config = _make_config(
        PortalEntry(name="GreenCo", platform="greenhouse", board_id="greenco", categories=["engineering"]),
        PortalEntry(name="LeverCo", platform="lever", board_id="leverco", categories=["engineering"]),
    )
    adapters = {"greenhouse": adapter_gh, "lever": adapter_lv}
    normalizers = {"greenhouse": FakeNormalizer(), "lever": FakeNormalizer()}
    bus = FakeEventBus()

    scanner = PortalScanner(config=config, adapters=adapters, normalizers=normalizers, event_bus=bus)
    result = await scanner.scan(ScanFilters())

    assert result.total_fetched == 2
    assert result.new == 2
    assert result.duplicates == 0
    assert len(result.jobs) == 2
    assert result.errors == []
    assert len(adapter_gh.calls) == 1
    assert len(adapter_lv.calls) == 1


@pytest.mark.asyncio
async def test_scan_filters_by_category() -> None:
    """Only portals whose categories overlap with the filter are scanned."""
    raw = _make_raw()
    adapter_eng = FakeAdapter([raw])
    adapter_design = FakeAdapter([raw])

    config = _make_config(
        PortalEntry(name="EngCo", platform="greenhouse", board_id="engco", categories=["engineering"]),
        PortalEntry(name="DesignCo", platform="lever", board_id="designco", categories=["design"]),
    )
    adapters = {"greenhouse": adapter_eng, "lever": adapter_design}
    normalizers = {"greenhouse": FakeNormalizer(), "lever": FakeNormalizer()}
    bus = FakeEventBus()

    scanner = PortalScanner(config=config, adapters=adapters, normalizers=normalizers, event_bus=bus)
    result = await scanner.scan(ScanFilters(categories=["engineering"]))

    assert result.new == 1
    assert len(adapter_eng.calls) == 1
    assert len(adapter_design.calls) == 0


@pytest.mark.asyncio
async def test_scan_filters_by_company() -> None:
    """Only portals whose name matches a company in the filter are scanned."""
    raw = _make_raw()
    adapter_a = FakeAdapter([raw])
    adapter_b = FakeAdapter([raw])

    config = _make_config(
        PortalEntry(name="CompanyA", platform="greenhouse", board_id="ca", categories=[]),
        PortalEntry(name="CompanyB", platform="lever", board_id="cb", categories=[]),
    )
    adapters = {"greenhouse": adapter_a, "lever": adapter_b}
    normalizers = {"greenhouse": FakeNormalizer(), "lever": FakeNormalizer()}
    bus = FakeEventBus()

    scanner = PortalScanner(config=config, adapters=adapters, normalizers=normalizers, event_bus=bus)
    result = await scanner.scan(ScanFilters(companies=["CompanyA"]))

    assert result.new == 1
    assert len(adapter_a.calls) == 1
    assert len(adapter_b.calls) == 0


@pytest.mark.asyncio
async def test_scan_deduplicates() -> None:
    """The same raw job returned twice yields new=1, duplicates=1."""
    raw = _make_raw("Engineer", "Acme", "https://example.com/1")
    adapter = FakeAdapter([raw, raw])

    config = _make_config(
        PortalEntry(name="Acme", platform="greenhouse", board_id="acme", categories=[]),
    )
    adapters = {"greenhouse": adapter}
    normalizers = {"greenhouse": FakeNormalizer("Engineer", "Acme", "https://example.com/1")}
    bus = FakeEventBus()

    scanner = PortalScanner(config=config, adapters=adapters, normalizers=normalizers, event_bus=bus)
    result = await scanner.scan(ScanFilters())

    assert result.total_fetched == 2
    assert result.new == 1
    assert result.duplicates == 1
    assert len(result.jobs) == 1


@pytest.mark.asyncio
async def test_scan_collects_errors() -> None:
    """When an adapter raises, the error is collected and scanning continues."""
    raw = _make_raw()
    adapter_ok = FakeAdapter([raw])
    adapter_bad = FakeAdapter(raise_on_fetch=True)

    config = _make_config(
        PortalEntry(name="GoodCo", platform="greenhouse", board_id="good", categories=[]),
        PortalEntry(name="BadCo", platform="lever", board_id="bad", categories=[]),
    )
    adapters = {"greenhouse": adapter_ok, "lever": adapter_bad}
    normalizers = {"greenhouse": FakeNormalizer(), "lever": FakeNormalizer()}
    bus = FakeEventBus()

    scanner = PortalScanner(config=config, adapters=adapters, normalizers=normalizers, event_bus=bus)
    result = await scanner.scan(ScanFilters())

    assert result.new == 1
    assert len(result.errors) == 1
    assert result.errors[0].portal == "BadCo"
    assert result.errors[0].platform == "lever"
    assert "network error" in result.errors[0].error


@pytest.mark.asyncio
async def test_scan_publishes_event_when_jobs_found() -> None:
    """A JobsIngestedEvent is published when at least one new job is found."""
    raw = _make_raw()
    adapter = FakeAdapter([raw])

    config = _make_config(
        PortalEntry(name="SomeCo", platform="greenhouse", board_id="someco", categories=[]),
    )
    adapters = {"greenhouse": adapter}
    normalizers = {"greenhouse": FakeNormalizer()}
    bus = FakeEventBus()

    scanner = PortalScanner(config=config, adapters=adapters, normalizers=normalizers, event_bus=bus)
    result = await scanner.scan(ScanFilters())

    assert result.new == 1
    assert len(bus.published) == 1
    event = bus.published[0]
    assert event.event_type == "jobs.ingested"
    assert event.payload["source"] == "portal_scan"
    assert len(event.payload["job_ids"]) == 1


@pytest.mark.asyncio
async def test_scan_no_event_when_no_new_jobs() -> None:
    """No event is published when no jobs are found."""
    adapter = FakeAdapter([])  # returns nothing

    config = _make_config(
        PortalEntry(name="EmptyCo", platform="greenhouse", board_id="empty", categories=[]),
    )
    adapters = {"greenhouse": adapter}
    normalizers = {"greenhouse": FakeNormalizer()}
    bus = FakeEventBus()

    scanner = PortalScanner(config=config, adapters=adapters, normalizers=normalizers, event_bus=bus)
    result = await scanner.scan(ScanFilters())

    assert result.new == 0
    assert bus.published == []

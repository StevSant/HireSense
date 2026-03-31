import asyncio

import pytest

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.kernel.events import DomainEvent
from hiresense.kernel.value_objects import SourceType


class FakeJobSource:
    def source_name(self) -> str:
        return "fake"

    def source_type(self) -> SourceType:
        return SourceType.API

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
    )
    result = await orchestrator.run()
    assert len(result) == 1
    assert result[0].title == "Engineer"

    await asyncio.sleep(0.05)
    assert len(events) == 1
    assert events[0].event_type == "jobs.ingested"

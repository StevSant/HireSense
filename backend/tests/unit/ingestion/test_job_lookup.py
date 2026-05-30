import uuid

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.ingestion.infrastructure import InMemoryJobsRepository


def _make_job(title: str = "SWE", company: str = "Acme") -> NormalizedJob:
    return NormalizedJob(
        id=str(uuid.uuid4()),
        title=title,
        company=company,
        description="desc",
        source="test",
        source_type="api",
        url="https://example.com",
    )


class FakeEventBus:
    async def publish(self, event) -> None:
        pass


def test_get_job_by_id_returns_none_initially() -> None:
    orchestrator = IngestionOrchestrator(
        sources=[], normalizers={}, event_bus=FakeEventBus(), repository=InMemoryJobsRepository()
    )
    assert orchestrator.get_job_by_id("nonexistent") is None


def test_store_and_retrieve_job() -> None:
    orchestrator = IngestionOrchestrator(
        sources=[], normalizers={}, event_bus=FakeEventBus(), repository=InMemoryJobsRepository()
    )
    job = _make_job()
    orchestrator.store_job(job)
    result = orchestrator.get_job_by_id(job.id)
    assert result is not None
    assert result.title == "SWE"


def test_store_multiple_and_retrieve() -> None:
    orchestrator = IngestionOrchestrator(
        sources=[], normalizers={}, event_bus=FakeEventBus(), repository=InMemoryJobsRepository()
    )
    job1 = _make_job("A", "X")
    job2 = _make_job("B", "Y")
    orchestrator.store_job(job1)
    orchestrator.store_job(job2)
    assert orchestrator.get_job_by_id(job1.id).title == "A"
    assert orchestrator.get_job_by_id(job2.id).title == "B"

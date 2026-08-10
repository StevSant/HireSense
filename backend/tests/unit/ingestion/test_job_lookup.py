import uuid

from hiresense.ingestion.domain import JobQueryService
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.infrastructure import InMemoryJobsRepository


def _make_job(
    title: str = "SWE", company: str = "Acme", url: str = "https://example.com"
) -> NormalizedJob:
    return NormalizedJob(
        id=str(uuid.uuid4()),
        title=title,
        company=company,
        description="desc",
        source="test",
        source_type="api",
        url=url,
    )


def test_get_job_by_id_returns_none_initially() -> None:
    job_query = JobQueryService(repository=InMemoryJobsRepository())
    assert job_query.get_job_by_id("nonexistent") is None


def test_store_and_retrieve_job() -> None:
    job_query = JobQueryService(repository=InMemoryJobsRepository())
    job = _make_job()
    job_query.store_job(job)
    result = job_query.get_job_by_id(job.id)
    assert result is not None
    assert result.title == "SWE"


def test_store_multiple_and_retrieve() -> None:
    job_query = JobQueryService(repository=InMemoryJobsRepository())
    job1 = _make_job("A", "X", url="https://example.com/a")
    job2 = _make_job("B", "Y", url="https://example.com/b")
    job_query.store_job(job1)
    job_query.store_job(job2)
    assert job_query.get_job_by_id(job1.id).title == "A"
    assert job_query.get_job_by_id(job2.id).title == "B"

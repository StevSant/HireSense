"""Unit tests for JobQueryService — the job-lookup / score-persistence seam
other bounded contexts hold instead of the whole IngestionOrchestrator.

Covers the full public surface: store_job, get_job_by_id, get_jobs_by_ids,
list_jobs (unfiltered + criteria), persist_scores, persist_scores_batch.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from hiresense.ingestion.domain import JobListCriteria, JobQueryService
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.infrastructure import InMemoryJobsRepository
from hiresense.ingestion.ports import ScoreUpdate


def _make_job(title: str = "SWE", company: str = "Acme", source: str = "test") -> NormalizedJob:
    return NormalizedJob(
        id=str(uuid.uuid4()),
        title=title,
        company=company,
        description="desc",
        source=source,
        source_type="api",
        url=f"https://example.com/{uuid.uuid4()}",
    )


def test_store_job_delegates_to_repository_upsert() -> None:
    repo = MagicMock()
    job = _make_job()

    JobQueryService(repository=repo).store_job(job)

    repo.upsert.assert_called_once_with(job)


def test_get_job_by_id_returns_stored_job() -> None:
    repo = InMemoryJobsRepository()
    service = JobQueryService(repository=repo)
    job = _make_job("Backend Engineer")
    service.store_job(job)

    stored = service.get_job_by_id(job.id)

    assert stored is not None
    assert stored.title == "Backend Engineer"


def test_get_job_by_id_returns_none_for_unknown_id() -> None:
    service = JobQueryService(repository=InMemoryJobsRepository())

    assert service.get_job_by_id("does-not-exist") is None


def test_get_jobs_by_ids_resolves_many_in_one_call() -> None:
    repo = InMemoryJobsRepository()
    service = JobQueryService(repository=repo)
    job_a = _make_job("A")
    job_b = _make_job("B")
    service.store_job(job_a)
    service.store_job(job_b)

    resolved = service.get_jobs_by_ids([job_a.id, job_b.id, "missing"])

    assert set(resolved) == {job_a.id, job_b.id}
    assert resolved[job_a.id].title == "A"
    assert resolved[job_b.id].title == "B"


def test_get_jobs_by_ids_with_empty_input_returns_empty_map() -> None:
    service = JobQueryService(repository=InMemoryJobsRepository())

    assert service.get_jobs_by_ids([]) == {}


def test_list_jobs_without_criteria_returns_full_corpus() -> None:
    repo = MagicMock()
    repo.list_all.return_value = []
    service = JobQueryService(repository=repo)

    service.list_jobs()

    repo.list_all.assert_called_once_with()
    repo.list_filtered.assert_not_called()


def test_list_jobs_with_criteria_pushes_predicates_to_the_repository() -> None:
    repo = MagicMock()
    repo.list_filtered.return_value = []
    service = JobQueryService(repository=repo)
    criteria = JobListCriteria(source="remotive")

    service.list_jobs(criteria)

    repo.list_filtered.assert_called_once_with(criteria)
    repo.list_all.assert_not_called()


def test_list_jobs_with_criteria_filters_against_the_in_memory_repo() -> None:
    repo = InMemoryJobsRepository()
    service = JobQueryService(repository=repo)
    service.store_job(_make_job("A", source="remotive"))
    service.store_job(_make_job("B", source="jobicy"))

    matched = service.list_jobs(JobListCriteria(source="remotive"))

    assert [job.title for job in matched] == ["A"]


def test_persist_scores_writes_a_single_job_score() -> None:
    repo = InMemoryJobsRepository()
    service = JobQueryService(repository=repo)
    job = _make_job()
    service.store_job(job)

    service.persist_scores(job.id, 0.42, 0.84)

    stored = service.get_job_by_id(job.id)
    assert stored is not None
    assert stored.match_score == pytest.approx(0.42)
    assert stored.semantic_score == pytest.approx(0.84)


def test_persist_scores_batch_delegates_to_bulk_update_scores() -> None:
    repo = MagicMock()
    service = JobQueryService(repository=repo)
    updates = [
        ScoreUpdate(job_id="a", match_score=0.8, semantic_score=0.9),
        ScoreUpdate(job_id="b", match_score=0.3, semantic_score=0.4),
    ]

    service.persist_scores_batch(updates)

    repo.bulk_update_scores.assert_called_once_with(updates)


def test_persist_scores_batch_reaches_the_store() -> None:
    repo = InMemoryJobsRepository()
    service = JobQueryService(repository=repo)
    job_a = _make_job("A")
    job_b = _make_job("B")
    service.store_job(job_a)
    service.store_job(job_b)

    service.persist_scores_batch(
        [
            ScoreUpdate(job_id=job_a.id, match_score=0.7, semantic_score=0.8),
            ScoreUpdate(job_id=job_b.id, match_score=0.2, semantic_score=0.3),
        ]
    )

    assert service.get_job_by_id(job_a.id).match_score == pytest.approx(0.7)
    assert service.get_job_by_id(job_b.id).semantic_score == pytest.approx(0.3)


def test_persist_scores_batch_empty_is_a_noop() -> None:
    service = JobQueryService(repository=InMemoryJobsRepository())

    service.persist_scores_batch([])  # must not raise


def test_shares_the_repository_it_is_given() -> None:
    """The service is a thin seam over a repository the orchestrator also
    writes through — a job ingested elsewhere must be visible immediately."""
    repo = InMemoryJobsRepository()
    job = _make_job("Ingested elsewhere")
    repo.upsert(job)

    assert JobQueryService(repository=repo).get_job_by_id(job.id) is not None

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.ingestion.infrastructure import InMemoryJobsRepository


def _make_job(title: str = "SWE", company: str = "Acme", url: str = "https://x/1") -> NormalizedJob:
    return NormalizedJob(
        id=str(uuid.uuid4()),
        title=title,
        company=company,
        description="desc",
        source="test",
        source_type="api",
        url=url,
    )


class _NoopBus:
    async def publish(self, event) -> None:  # noqa: ARG002
        pass


def test_add_if_absent_skips_duplicate_dedup_key() -> None:
    repo = InMemoryJobsRepository()
    job1 = _make_job()
    # Same dedup_key inputs, different id — must be skipped.
    job2 = NormalizedJob(**{**job1.model_dump(), "id": str(uuid.uuid4())})

    assert repo.add_if_absent(job1) is True
    assert repo.add_if_absent(job2) is False
    assert len(repo.list_all()) == 1
    assert repo.list_all()[0].id == job1.id


def test_update_scores_persists_to_listed_job() -> None:
    repo = InMemoryJobsRepository()
    job = _make_job()
    repo.add_if_absent(job)

    repo.update_scores(job.id, match_score=0.42, semantic_score=0.7)

    stored = repo.get_by_id(job.id)
    assert stored is not None
    assert stored.match_score == pytest.approx(0.42)
    assert stored.semantic_score == pytest.approx(0.7)


def test_prune_older_than_removes_only_stale_rows() -> None:
    repo = InMemoryJobsRepository()
    repo.add_if_absent(_make_job(title="A"))
    repo.add_if_absent(_make_job(title="B"))

    # Cutoff in the future — everything is "older" than that.
    future_cutoff = datetime.now(timezone.utc) + timedelta(days=1)
    removed = repo.prune_older_than(future_cutoff)
    assert removed == 2
    assert repo.list_all() == []


def test_prune_older_than_keeps_recent_rows() -> None:
    repo = InMemoryJobsRepository()
    repo.add_if_absent(_make_job(title="A"))

    past_cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    removed = repo.prune_older_than(past_cutoff)
    assert removed == 0
    assert len(repo.list_all()) == 1


@pytest.mark.asyncio
async def test_orchestrator_skips_duplicate_across_runs() -> None:
    from hiresense.ingestion.domain.models import RawJobListing
    from hiresense.kernel.value_objects import SourceType

    class FakeSource:
        def source_name(self) -> str:
            return "fake"

        def source_type(self) -> SourceType:
            return SourceType.API

        async def fetch_jobs(self, filters=None) -> list[RawJobListing]:  # noqa: ARG002
            return [
                RawJobListing(
                    source="fake",
                    source_id="1",
                    raw_data={"title": "X", "company": "Y", "url": "https://x/1"},
                )
            ]

    class FakeNormalizer:
        def normalize(self, raw: RawJobListing) -> dict:
            return {
                "title": raw.raw_data["title"],
                "company": raw.raw_data["company"],
                "description": "",
                "skills": [],
                "location": "",
                "salary_range": None,
                "url": raw.raw_data["url"],
                "language": "en",
            }

    repo = InMemoryJobsRepository()
    orchestrator = IngestionOrchestrator(
        sources=[FakeSource()],
        normalizers={"fake": FakeNormalizer()},
        event_bus=_NoopBus(),
        cooldown_seconds=0,
        repository=repo,
    )

    first = await orchestrator.run()
    second = await orchestrator.run()

    assert len(first) == 1
    # Second run sees the same source data — dedup skips it.
    assert second == []
    assert len(repo.list_all()) == 1

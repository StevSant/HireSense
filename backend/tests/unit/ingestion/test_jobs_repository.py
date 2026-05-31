from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.infrastructure.database import Base
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.infrastructure import InMemoryJobsRepository
from hiresense.ingestion.infrastructure.jobs_repository import JobsRepository
from hiresense.ingestion.infrastructure.models import IngestedJob  # noqa: F401 (registers table)


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


def test_upsert_skips_duplicate_identity() -> None:
    repo = InMemoryJobsRepository()
    job1 = _make_job()
    # Same identity inputs (source + url), different id — must be deduped.
    job2 = NormalizedJob(**{**job1.model_dump(), "id": str(uuid.uuid4())})

    assert repo.upsert(job1) == UpsertResult.INSERTED
    assert repo.upsert(job2) == UpsertResult.UNCHANGED
    assert len(repo.list_all()) == 1
    assert repo.list_all()[0].id == job1.id


def test_update_scores_persists_to_listed_job() -> None:
    repo = InMemoryJobsRepository()
    job = _make_job()
    repo.upsert(job)

    repo.update_scores(job.id, match_score=0.42, semantic_score=0.7)

    stored = repo.get_by_id(job.id)
    assert stored is not None
    assert stored.match_score == pytest.approx(0.42)
    assert stored.semantic_score == pytest.approx(0.7)


def test_prune_older_than_removes_only_stale_rows() -> None:
    repo = InMemoryJobsRepository()
    repo.upsert(_make_job(title="A", url="https://x/a"))
    repo.upsert(_make_job(title="B", url="https://x/b"))

    # Cutoff in the future — everything is "older" than that.
    future_cutoff = datetime.now(timezone.utc) + timedelta(days=1)
    removed = repo.prune_older_than(future_cutoff)
    assert len(removed) == 2  # returns deleted ids (for vector eviction)
    assert repo.list_all() == []


def test_prune_older_than_keeps_recent_rows() -> None:
    repo = InMemoryJobsRepository()
    repo.upsert(_make_job(title="A"))

    past_cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    removed = repo.prune_older_than(past_cutoff)
    assert removed == []
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

        def supports_snapshot_closure(self) -> bool:
            return False

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


@pytest.fixture
def sync_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)


@pytest.fixture
def repo(sync_session_factory):
    return JobsRepository(session_factory=sync_session_factory, bucket="boards")


def _job(repo_id: str, **over):
    base = dict(
        id=repo_id, title="Engineer", company="Acme", description="D",
        source="remotive", source_type="api", url="https://e.com/1",
        source_id="native-1",
    )
    base.update(over)
    return NormalizedJob(**base)


def test_upsert_inserts_then_unchanged(repo):  # `repo` = existing fixture/sync repo
    assert repo.upsert(_job("a")) == UpsertResult.INSERTED
    assert repo.upsert(_job("b")) == UpsertResult.UNCHANGED  # same identity+content


def test_upsert_updates_changed_fields_and_preserves_id(repo):
    repo.upsert(_job("a"))
    assert repo.upsert(_job("b", salary_range="$200k")) == UpsertResult.UPDATED
    stored = repo.list_all()
    assert len(stored) == 1
    assert stored[0].id == "a"               # original id preserved
    assert stored[0].salary_range == "$200k" # field updated


def test_upsert_reopens_a_closed_job(repo):
    repo.upsert(_job("a"))
    closed = repo.list_all()[0].id
    repo.mark_closed([closed])
    result = repo.upsert(_job("b"))           # same identity re-seen
    assert result == UpsertResult.REOPENED    # signals caller to re-index
    assert repo.list_all()[0].status == "open"


def test_in_memory_repo_upsert_parity():
    mem = InMemoryJobsRepository()
    assert mem.upsert(_job("a")) == UpsertResult.INSERTED
    assert mem.upsert(_job("b")) == UpsertResult.UNCHANGED
    assert mem.upsert(_job("c", salary_range="$200k")) == UpsertResult.UPDATED
    stored = mem.list_all()
    assert len(stored) == 1 and stored[0].id == "a" and stored[0].salary_range == "$200k"
    mem.mark_closed(["a"])
    assert mem.upsert(_job("d")) == UpsertResult.REOPENED
    assert mem.list_all()[0].status == "open"


def test_bump_missed_and_close_persists_per_row(repo):
    from hiresense.ingestion.domain.identity import identity_key

    seen_job = _job("a", source_id="n1", url="https://e.com/1")
    gone_job = _job("b", source_id="n2", url="https://e.com/2")
    repo.upsert(seen_job)
    repo.upsert(gone_job)

    # Only seen_job is present in this fetch; threshold 1 closes the missing one immediately.
    closed = repo.bump_missed_and_close(
        "remotive", {identity_key(seen_job)}, threshold=1
    )

    by_sid = {j.source_id: j for j in repo.list_all()}
    assert by_sid["n2"].id in closed
    assert by_sid["n2"].status == "closed"     # missing -> closed
    assert by_sid["n1"].status == "open"       # seen -> stays open


def test_find_open_stale_prioritizes_unchecked_and_caps(repo):
    for i in range(3):
        repo.upsert(_job(str(i), source_id=f"n{i}", url=f"https://e.com/{i}"))
    assert len(repo.find_open_stale(["remotive"], limit=2)) == 2  # cap respected
    repo.mark_checked([j.id for j in repo.list_all()])
    repo.upsert(_job("new", source_id="nnew", url="https://e.com/new"))  # last_checked None
    stale = repo.find_open_stale(["remotive"], limit=1)
    assert len(stale) == 1 and stale[0].source_id == "nnew"  # NULLS FIRST


def test_find_open_stale_excludes_closed_and_other_sources(repo):
    repo.upsert(_job("a", source_id="n1", url="https://e.com/1"))               # remotive
    repo.upsert(_job("b", source="other", source_id="n2", url="https://e.com/2"))
    a_id = next(j.id for j in repo.list_all() if j.source == "remotive")
    repo.mark_closed([a_id])
    assert repo.find_open_stale(["remotive"], 5) == []     # closed excluded
    assert len(repo.find_open_stale(["other"], 5)) == 1    # different source, open


def test_find_open_stale_in_memory_parity():
    mem = InMemoryJobsRepository()
    mem.upsert(_job("a", source_id="n1", url="https://e.com/1"))
    mem.upsert(_job("b", source_id="n2", url="https://e.com/2"))
    assert len(mem.find_open_stale(["remotive"], 5)) == 2
    mem.mark_closed([mem.list_all()[0].id])
    assert len(mem.find_open_stale(["remotive"], 5)) == 1


@pytest.mark.asyncio
async def test_prune_evicts_pruned_vectors_from_index() -> None:
    """#19 item 2: age-pruned jobs are removed from the vector store too."""
    from datetime import datetime, timezone

    repo = InMemoryJobsRepository()
    job = _job("a", source_id="n1", url="https://e.com/1")
    repo.upsert(job)
    repo._fetched_at[job.id] = datetime(2000, 1, 1, tzinfo=timezone.utc)  # backdate

    class _FakeIndexer:
        def __init__(self) -> None:
            self.removed: list[list[str]] = []

        async def index(self, jobs):
            return 0

        async def remove(self, ids):
            self.removed.append(list(ids))

    idx = _FakeIndexer()
    orch = IngestionOrchestrator(
        sources=[], normalizers={}, event_bus=_NoopBus(),
        repository=repo, retention_days=1, indexer=idx, cooldown_seconds=0,
    )
    await orch._prune_expired()

    assert repo.list_all() == []
    assert idx.removed == [[job.id]]

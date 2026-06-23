from __future__ import annotations

import pytest

from hiresense.ingestion.domain.job_revalidation_service import JobRevalidationService
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.infrastructure import InMemoryJobsRepository


class _Resp:
    def __init__(self, code: int, text: str = "") -> None:
        self.status_code = code
        self.text = text


class _Client:
    def __init__(self, by_url: dict[str, _Resp], *, raise_urls: set[str] | None = None) -> None:
        self._by_url = by_url
        self._raise = raise_urls or set()
        self.requested: list[str] = []

    async def get(self, url: str, **kwargs) -> _Resp:
        self.requested.append(url)
        if url in self._raise:
            raise RuntimeError("timeout")
        return self._by_url[url]


class _Indexer:
    def __init__(self) -> None:
        self.removed: list[list[str]] = []

    async def remove(self, ids) -> None:
        self.removed.append(list(ids))


def _job(sid: str, url: str) -> NormalizedJob:
    return NormalizedJob(
        id=sid, title="Engineer", company="Acme", description="D",
        source="remotive", source_type="api", url=url, source_id=sid,
    )


def _seed() -> tuple[InMemoryJobsRepository, NormalizedJob, NormalizedJob]:
    repo = InMemoryJobsRepository()
    a = _job("a", "https://e.com/a")
    b = _job("b", "https://e.com/b")
    repo.upsert(a)
    repo.upsert(b)
    return repo, a, b


@pytest.mark.asyncio
async def test_sweep_closes_404_keeps_200_and_marks_checked() -> None:
    repo, a, b = _seed()
    client = _Client({a.url: _Resp(200, "Apply now"), b.url: _Resp(404)})
    indexer = _Indexer()
    svc = JobRevalidationService(
        http_client=client, repository=repo, indexer=indexer,
        sources=["remotive"], markers=["closed"], batch=10, concurrency=2, delay=0.0,
    )

    closed = await svc.sweep()

    statuses = {j.id: j.status for j in repo.list_all()}
    assert statuses["b"] == "closed" and statuses["a"] == "open"
    assert closed == ["b"]
    assert indexer.removed == [["b"]]


@pytest.mark.asyncio
async def test_sweep_closes_on_content_marker() -> None:
    repo, a, b = _seed()
    client = _Client({
        a.url: _Resp(200, "Apply now"),
        b.url: _Resp(200, "This position has been FILLED."),
    })
    svc = JobRevalidationService(
        http_client=client, repository=repo, indexer=None,
        sources=["remotive"], markers=["has been filled"], batch=10, concurrency=2, delay=0.0,
    )
    closed = await svc.sweep()
    assert closed == ["b"]
    assert {j.id: j.status for j in repo.list_all()}["b"] == "closed"


@pytest.mark.asyncio
async def test_sweep_request_error_is_unknown_not_closed() -> None:
    repo, a, b = _seed()
    client = _Client({a.url: _Resp(200, "ok")}, raise_urls={b.url})
    svc = JobRevalidationService(
        http_client=client, repository=repo, indexer=None,
        sources=["remotive"], markers=[], batch=10, concurrency=1, delay=0.0,
    )
    closed = await svc.sweep()
    assert closed == []  # a network error must NOT close the job
    assert all(j.status == "open" for j in repo.list_all())


@pytest.mark.asyncio
async def test_probe_url_builder_overrides_listing_url_per_source() -> None:
    """LinkedIn closure lives on its guest API, not the public /jobs/view URL.
    A per-source probe_url_builder must redirect the probe to the guest endpoint
    (built from source_id) while other sources keep probing job.url."""
    repo = InMemoryJobsRepository()
    li = NormalizedJob(
        id="li", title="E", company="C", description="D", source="linkedin",
        source_type="scraper", url="https://www.linkedin.com/jobs/view/999", source_id="999",
    )
    other = _job("other", "https://e.com/o")  # source=remotive
    repo.upsert(li)
    repo.upsert(other)

    guest_url = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/999"
    client = _Client({
        guest_url: _Resp(200, "No longer accepting applications"),
        other.url: _Resp(200, "Apply now"),
    })
    svc = JobRevalidationService(
        http_client=client, repository=repo, indexer=None,
        sources=["linkedin", "remotive"], markers=["no longer accepting applications"],
        batch=10, concurrency=2, delay=0.0,
        probe_url_builders={
            "linkedin": lambda job: f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job.source_id}",
        },
    )

    closed = await svc.sweep()

    assert closed == ["li"]  # probed the guest URL and saw the closure marker
    assert guest_url in client.requested  # NOT the public /jobs/view URL
    assert "https://www.linkedin.com/jobs/view/999" not in client.requested
    assert {j.id: j.status for j in repo.list_all()}["other"] == "open"


@pytest.mark.asyncio
async def test_sweep_covers_whole_corpus_across_chunks() -> None:
    """`batch` caps each chunk, but the sweep loops until EVERY open job is
    probed — so a small batch still covers the full corpus (all platforms)."""
    repo = InMemoryJobsRepository()
    jobs = [_job(f"j{i}", f"https://e.com/{i}") for i in range(5)]
    for j in jobs:
        repo.upsert(j)
    responses = {j.url: _Resp(200, "ok") for j in jobs}
    responses[jobs[3].url] = _Resp(404)  # one dead listing anywhere in the corpus
    client = _Client(responses)
    svc = JobRevalidationService(
        http_client=client, repository=repo, indexer=None,
        sources=["remotive"], markers=[], batch=2, concurrency=2, delay=0.0,
    )

    closed = await svc.sweep()

    assert closed == ["j3"]
    # Each of the 5 jobs probed exactly once despite batch=2 (loops 3 chunks).
    assert sorted(client.requested) == sorted(j.url for j in jobs)


@pytest.mark.asyncio
async def test_revalidate_ids_probes_only_requested_probeable_open_jobs() -> None:
    """Targeted probe: closes a requested dead job, ignores a requested job from
    a non-probeable source, and never touches jobs that weren't requested."""
    repo = InMemoryJobsRepository()
    dead = _job("dead", "https://e.com/dead")  # remotive (probeable)
    alive = _job("alive", "https://e.com/alive")  # remotive, requested but open
    hn = NormalizedJob(
        id="hn", title="E", company="C", description="D", source="hn_hiring",
        source_type="api", url="https://news.ycombinator.com/item?id=1", source_id="1",
    )
    untouched = _job("untouched", "https://e.com/untouched")
    for job in (dead, alive, hn, untouched):
        repo.upsert(job)

    client = _Client({
        dead.url: _Resp(404),
        alive.url: _Resp(200, "Apply now"),
        hn.url: _Resp(404),  # would close IF probed — but hn_hiring isn't probeable
    })
    svc = JobRevalidationService(
        http_client=client, repository=repo, indexer=None,
        sources=["remotive"], markers=[], batch=10, concurrency=2, delay=0.0,
    )

    closed = await svc.revalidate_ids(["dead", "alive", "hn"])

    assert closed == ["dead"]
    statuses = {j.id: j.status for j in repo.list_all()}
    assert statuses["dead"] == "closed"
    assert statuses["alive"] == "open"
    assert statuses["hn"] == "open"  # non-probeable source skipped
    assert hn.url not in client.requested
    assert untouched.url not in client.requested  # not requested → not probed


@pytest.mark.asyncio
async def test_sweep_empty_when_no_open_jobs() -> None:
    repo = InMemoryJobsRepository()
    client = _Client({})
    svc = JobRevalidationService(
        http_client=client, repository=repo, indexer=None,
        sources=["remotive"], markers=[], batch=10, concurrency=1, delay=0.0,
    )
    assert await svc.sweep() == []
    assert client.requested == []

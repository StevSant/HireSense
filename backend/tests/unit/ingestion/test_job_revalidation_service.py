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
async def test_sweep_empty_when_no_open_jobs() -> None:
    repo = InMemoryJobsRepository()
    client = _Client({})
    svc = JobRevalidationService(
        http_client=client, repository=repo, indexer=None,
        sources=["remotive"], markers=[], batch=10, concurrency=1, delay=0.0,
    )
    assert await svc.sweep() == []
    assert client.requested == []

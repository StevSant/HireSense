from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hiresense.ingestion.domain.closed_listing_classifier import closure_reason
from hiresense.ingestion.domain.job_closure_reason import JobClosureReason
from hiresense.ingestion.domain.job_revalidation_service import JobRevalidationService
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.infrastructure import InMemoryJobsRepository


def _allow_all(_url: str) -> bool:
    """Permissive SSRF guard for tests that aren't exercising the guard itself
    (keeps the suite offline — the real guard resolves DNS)."""
    return True


class _Resp:
    def __init__(self, code: int, text: str = "", location: str | None = None) -> None:
        self.status_code = code
        self.text = text
        self._body = text.encode()
        self.headers: dict[str, str] = {"location": location} if location else {}
        self.encoding = "utf-8"

    async def aiter_bytes(self, chunk_size: int = 65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]


class _StreamCtx:
    def __init__(self, client: _Client, url: str, headers: dict[str, str]) -> None:
        self._client = client
        self._url = url
        self._headers = headers

    async def __aenter__(self) -> _Resp:
        self._client.requested.append(self._url)
        self._client.headers_seen.append(self._headers or {})
        if self._url in self._client._raise:
            raise RuntimeError("timeout")
        return self._client._by_url[self._url]

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _Client:
    def __init__(self, by_url: dict[str, _Resp], *, raise_urls: set[str] | None = None) -> None:
        self._by_url = by_url
        self._raise = raise_urls or set()
        self.requested: list[str] = []
        self.headers_seen: list[dict[str, str]] = []

    def stream(self, method: str, url: str, **kwargs) -> _StreamCtx:
        return _StreamCtx(self, url, kwargs.get("headers") or {})


class _FakeHistory:
    """Records every `record_closures` call verbatim for assertion."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], JobClosureReason, str | None]] = []

    def record_closures(
        self,
        job_ids: list[str],
        reason: JobClosureReason,
        run_id: str | None = None,
    ) -> None:
        self.calls.append((list(job_ids), reason, run_id))


def _job(sid: str, url: str) -> NormalizedJob:
    return NormalizedJob(
        id=sid,
        title="Engineer",
        company="Acme",
        description="D",
        source="remotive",
        source_type="api",
        url=url,
        source_id=sid,
    )


def _seed() -> tuple[InMemoryJobsRepository, NormalizedJob, NormalizedJob]:
    repo = InMemoryJobsRepository()
    a = _job("a", "https://e.com/a")
    b = _job("b", "https://e.com/b")
    repo.upsert(a)
    repo.upsert(b)
    return repo, a, b


def test_closure_reason_maps_404_and_410_to_probe_404() -> None:
    assert closure_reason(404) == JobClosureReason.PROBE_404
    assert closure_reason(410) == JobClosureReason.PROBE_404


def test_closure_reason_maps_a_200_marker_hit_to_closed_marker() -> None:
    assert closure_reason(200) == JobClosureReason.CLOSED_MARKER


@pytest.mark.asyncio
async def test_a_404_probe_records_probe_404() -> None:
    repo, a, b = _seed()
    client = _Client({a.url: _Resp(200, "Apply now"), b.url: _Resp(404)})
    history = _FakeHistory()
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=["closed"],
        batch=10,
        concurrency=2,
        delay=0.0,
        url_guard=_allow_all,
        history=history,
    )

    closed = await svc.sweep()

    assert closed == ["b"]
    assert history.calls == [(["b"], JobClosureReason.PROBE_404, None)]


@pytest.mark.asyncio
async def test_a_dead_end_redirect_records_dead_end_redirect() -> None:
    repo, a, b = _seed()
    client = _Client(
        {
            a.url: _Resp(200, "Apply now"),
            b.url: _Resp(301, location="https://e.com/"),
            "https://e.com/": _Resp(200, "Browse thousands of remote jobs"),
        }
    )
    history = _FakeHistory()
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=["closed"],
        batch=10,
        concurrency=1,
        delay=0.0,
        url_guard=_allow_all,
        history=history,
    )

    closed = await svc.sweep()

    assert closed == ["b"]
    assert history.calls == [(["b"], JobClosureReason.DEAD_END_REDIRECT, None)]


@pytest.mark.asyncio
async def test_a_200_closed_marker_records_closed_marker() -> None:
    repo, a, b = _seed()
    client = _Client(
        {
            a.url: _Resp(200, "Apply now"),
            b.url: _Resp(200, "This position has been FILLED."),
        }
    )
    history = _FakeHistory()
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=["has been filled"],
        batch=10,
        concurrency=2,
        delay=0.0,
        url_guard=_allow_all,
        history=history,
    )

    closed = await svc.sweep()

    assert closed == ["b"]
    assert history.calls == [(["b"], JobClosureReason.CLOSED_MARKER, None)]


@pytest.mark.asyncio
async def test_expiry_closures_record_expiry() -> None:
    now = datetime(2026, 7, 4, tzinfo=timezone.utc)
    repo = InMemoryJobsRepository()
    expired = NormalizedJob(
        id="exp",
        title="E",
        company="C",
        description="D",
        source="himalayas",
        source_type="api",
        url="https://himalayas.app/x",
        source_id="exp",
        expiry_date=now - timedelta(days=1),
    )
    repo.upsert(expired)
    client = _Client({})
    history = _FakeHistory()
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=[],
        batch=10,
        concurrency=2,
        delay=0.0,
        url_guard=_allow_all,
        clock=lambda: now,
        history=history,
    )

    closed = await svc.sweep()

    assert closed == ["exp"]
    assert history.calls == [(["exp"], JobClosureReason.EXPIRY, None)]


@pytest.mark.asyncio
async def test_sweep_closures_are_recorded_with_no_run_id() -> None:
    """The URL-probe sweep is not an ingestion run — every closure it records
    must carry run_id=None, never a synthetic run attached after the fact."""
    repo, a, b = _seed()
    client = _Client({a.url: _Resp(200, "Apply now"), b.url: _Resp(404)})
    history = _FakeHistory()
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=["closed"],
        batch=10,
        concurrency=2,
        delay=0.0,
        url_guard=_allow_all,
        history=history,
    )

    await svc.sweep()

    assert all(run_id is None for _, _, run_id in history.calls)


@pytest.mark.asyncio
async def test_an_open_verdict_records_nothing() -> None:
    repo, a, b = _seed()
    client = _Client({a.url: _Resp(200, "Apply now"), b.url: _Resp(200, "Apply now")})
    history = _FakeHistory()
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=["closed"],
        batch=10,
        concurrency=2,
        delay=0.0,
        url_guard=_allow_all,
        history=history,
    )

    closed = await svc.sweep()

    assert closed == []
    assert history.calls == []


@pytest.mark.asyncio
async def test_service_without_a_recorder_still_sweeps() -> None:
    repo, a, b = _seed()
    client = _Client({a.url: _Resp(200, "Apply now"), b.url: _Resp(404)})
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=["closed"],
        batch=10,
        concurrency=2,
        delay=0.0,
        url_guard=_allow_all,
    )

    closed = await svc.sweep()

    assert closed == ["b"]

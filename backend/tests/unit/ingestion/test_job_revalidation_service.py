from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

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


class _Indexer:
    def __init__(self) -> None:
        self.removed: list[list[str]] = []

    async def remove(self, ids) -> None:
        self.removed.append(list(ids))


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


@pytest.mark.asyncio
async def test_sweep_closes_404_keeps_200_and_marks_checked() -> None:
    repo, a, b = _seed()
    client = _Client({a.url: _Resp(200, "Apply now"), b.url: _Resp(404)})
    indexer = _Indexer()
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=indexer,
        sources=["remotive"],
        markers=["closed"],
        batch=10,
        concurrency=2,
        delay=0.0,
        url_guard=_allow_all,
    )

    closed = await svc.sweep()

    statuses = {j.id: j.status for j in repo.list_all()}
    assert statuses["b"] == "closed" and statuses["a"] == "open"
    assert closed == ["b"]
    assert indexer.removed == [["b"]]


@pytest.mark.asyncio
async def test_sweep_closes_on_content_marker() -> None:
    repo, a, b = _seed()
    client = _Client(
        {
            a.url: _Resp(200, "Apply now"),
            b.url: _Resp(200, "This position has been FILLED."),
        }
    )
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
    )
    closed = await svc.sweep()
    assert closed == ["b"]
    assert {j.id: j.status for j in repo.list_all()}["b"] == "closed"


@pytest.mark.asyncio
async def test_sweep_request_error_is_unknown_not_closed() -> None:
    repo, a, b = _seed()
    client = _Client({a.url: _Resp(200, "ok")}, raise_urls={b.url})
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=[],
        batch=10,
        concurrency=1,
        delay=0.0,
        url_guard=_allow_all,
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
        id="li",
        title="E",
        company="C",
        description="D",
        source="linkedin",
        source_type="scraper",
        url="https://www.linkedin.com/jobs/view/999",
        source_id="999",
    )
    other = _job("other", "https://e.com/o")  # source=remotive
    repo.upsert(li)
    repo.upsert(other)

    guest_url = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/999"
    client = _Client(
        {
            guest_url: _Resp(200, "No longer accepting applications"),
            other.url: _Resp(200, "Apply now"),
        }
    )
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["linkedin", "remotive"],
        markers=["no longer accepting applications"],
        batch=10,
        concurrency=2,
        delay=0.0,
        url_guard=_allow_all,
        probe_url_builders={
            "linkedin": lambda job: (
                f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job.source_id}"
            ),
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
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=[],
        batch=2,
        concurrency=2,
        delay=0.0,
        url_guard=_allow_all,
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
        id="hn",
        title="E",
        company="C",
        description="D",
        source="hn_hiring",
        source_type="api",
        url="https://news.ycombinator.com/item?id=1",
        source_id="1",
    )
    untouched = _job("untouched", "https://e.com/untouched")
    for job in (dead, alive, hn, untouched):
        repo.upsert(job)

    client = _Client(
        {
            dead.url: _Resp(404),
            alive.url: _Resp(200, "Apply now"),
            hn.url: _Resp(404),  # would close IF probed — but hn_hiring isn't probeable
        }
    )
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
async def test_probe_forwards_configured_user_agent_header() -> None:
    """Some listing hosts 403 the default python-httpx UA, masking a real
    signal as UNKNOWN. A configured UA must be sent on every probe."""
    repo, a, b = _seed()
    client = _Client({a.url: _Resp(200, "ok"), b.url: _Resp(200, "ok")})
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
        user_agent="TestUA/1.0",
    )

    await svc.sweep()

    assert client.headers_seen  # jobs were probed
    assert all(h.get("User-Agent") == "TestUA/1.0" for h in client.headers_seen)
    assert all("Accept" in h for h in client.headers_seen)


@pytest.mark.asyncio
async def test_probe_sends_no_headers_without_configured_user_agent() -> None:
    """Absent a configured UA, probes stay header-free (backward compatible)."""
    repo, a, b = _seed()
    client = _Client({a.url: _Resp(200, "ok"), b.url: _Resp(200, "ok")})
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
    )

    await svc.sweep()

    assert client.headers_seen
    assert all(h == {} for h in client.headers_seen)


@pytest.mark.asyncio
async def test_sweep_closes_expired_jobs_without_probing() -> None:
    """Sources whose pages block probes (himalayas) carry a source-declared
    expiry_date. The sweep closes them DB-side — no HTTP — even though they are
    NOT in the probeable `sources` set, and evicts them from the index."""
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
    live = NormalizedJob(
        id="live",
        title="E",
        company="C",
        description="D",
        source="himalayas",
        source_type="api",
        url="https://himalayas.app/y",
        source_id="live",
        expiry_date=now + timedelta(days=1),
    )
    repo.upsert(expired)
    repo.upsert(live)
    client = _Client({})  # himalayas not probeable → no probe responses needed
    indexer = _Indexer()
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=indexer,
        sources=["remotive"],
        markers=[],
        batch=10,
        concurrency=2,
        delay=0.0,
        url_guard=_allow_all,
        clock=lambda: now,
    )

    closed = await svc.sweep()

    assert closed == ["exp"]
    statuses = {j.id: j.status for j in repo.list_all()}
    assert statuses["exp"] == "closed" and statuses["live"] == "open"
    assert indexer.removed == [["exp"]]  # evicted from the vector index
    assert client.requested == []  # expiry closure is DB-side, no HTTP probe


@pytest.mark.asyncio
async def test_sweep_empty_when_no_open_jobs() -> None:
    repo = InMemoryJobsRepository()
    client = _Client({})
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=[],
        batch=10,
        concurrency=1,
        delay=0.0,
        url_guard=_allow_all,
    )
    assert await svc.sweep() == []
    assert client.requested == []


# --- SSRF hardening (#134) ---


@pytest.mark.asyncio
async def test_probe_blocks_private_target_pre_request_and_leaves_open() -> None:
    """A job whose URL resolves to a private address is refused BEFORE any
    request — the fake is never hit — and the job stays open (UNKNOWN)."""
    repo = InMemoryJobsRepository()
    internal = _job("internal", "http://169.254.169.254/latest/meta-data/")
    repo.upsert(internal)
    client = _Client({internal.url: _Resp(404)})  # would close IF ever probed

    def guard(url: str) -> bool:
        return "169.254.169.254" not in url

    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=[],
        batch=10,
        concurrency=1,
        delay=0.0,
        url_guard=guard,
    )

    closed = await svc.sweep()

    assert closed == []  # blocked probe is UNKNOWN, never a closure
    assert {j.id: j.status for j in repo.list_all()}["internal"] == "open"
    assert client.requested == []  # refused before the HTTP call


@pytest.mark.asyncio
async def test_probe_blocks_redirect_to_private_target() -> None:
    """An allowlisted host that 302s to an internal address is refused on the
    redirect hop — the internal target is never fetched and the job stays open."""
    repo = InMemoryJobsRepository()
    job = _job("j", "https://public.example/listing")
    repo.upsert(job)
    internal = "http://10.0.0.5/admin"
    client = _Client(
        {
            job.url: _Resp(302, location=internal),
            internal: _Resp(404),  # a closure signal IF the hop were followed
        }
    )

    def guard(url: str) -> bool:
        return "10.0.0.5" not in url

    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=[],
        batch=10,
        concurrency=1,
        delay=0.0,
        max_redirects=5,
        url_guard=guard,
    )

    closed = await svc.sweep()

    assert closed == []  # the internal 404 must not close the job
    assert {j.id: j.status for j in repo.list_all()}["j"] == "open"
    assert job.url in client.requested  # the public hop was fetched
    assert internal not in client.requested  # the internal hop was refused


@pytest.mark.asyncio
async def test_probe_follows_allowed_redirect_to_closure() -> None:
    """A redirect to another PUBLIC target is followed and its closure signal
    (404) applied — manual redirect handling still detects closures."""
    repo = InMemoryJobsRepository()
    job = _job("j", "https://public.example/old")
    repo.upsert(job)
    moved = "https://public.example/new"
    client = _Client({job.url: _Resp(301, location=moved), moved: _Resp(404)})
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=[],
        batch=10,
        concurrency=1,
        delay=0.0,
        max_redirects=5,
        url_guard=_allow_all,
    )

    closed = await svc.sweep()

    assert closed == ["j"]
    assert moved in client.requested


@pytest.mark.asyncio
async def test_probe_redirect_loop_exceeding_cap_is_unknown() -> None:
    """A redirect chain longer than max_redirects is refused (UNKNOWN), never
    followed forever."""
    repo = InMemoryJobsRepository()
    job = _job("j", "https://public.example/a")
    repo.upsert(job)
    client = _Client({job.url: _Resp(302, location=job.url)})  # self-redirect loop
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=[],
        batch=10,
        concurrency=1,
        delay=0.0,
        max_redirects=2,
        url_guard=_allow_all,
    )

    closed = await svc.sweep()

    assert closed == []  # loop capped → UNKNOWN → stays open
    assert {j.id: j.status for j in repo.list_all()}["j"] == "open"


@pytest.mark.asyncio
async def test_probe_body_read_is_capped() -> None:
    """A closure marker positioned beyond max_probe_bytes is NOT seen — the body
    read is truncated, so an adversarial huge page can't exhaust memory (and a
    marker past the cap can't drive a false closure)."""
    repo, a, b = _seed()
    # Marker sits after 20 filler bytes; the cap reads only the first 5.
    body = "x" * 20 + "this job is closed"
    client = _Client({a.url: _Resp(200, "ok"), b.url: _Resp(200, body)})
    svc = JobRevalidationService(
        http_client=client,
        repository=repo,
        indexer=None,
        sources=["remotive"],
        markers=["this job is closed"],
        batch=10,
        concurrency=1,
        delay=0.0,
        max_probe_bytes=5,
        url_guard=_allow_all,
    )

    closed = await svc.sweep()

    assert closed == []  # marker beyond the cap was never read
    assert all(j.status == "open" for j in repo.list_all())

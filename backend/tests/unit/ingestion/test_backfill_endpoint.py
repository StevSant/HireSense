"""Tests for POST /ingestion/backfill-embeddings endpoint.

TDD red-first: these tests are written before implementation. They verify:
  1. Production-path wiring: real attribute names on SharedInfra/IngestionProvider.
  2. Auth gate: 401 without Bearer token.
  3. Idempotency: running twice produces the same upsert state (no duplicates).
  4. Empty corpus / unavailable vector store: returns counts=0, no crash.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.domain import AuthService
from hiresense.ingestion.api import router
from hiresense.ingestion.api.dependencies import get_backfill_service
from hiresense.ingestion.domain.embedding_backfill_service import EmbeddingBackfillService
from hiresense.ingestion.domain.models import NormalizedJob


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _job(job_id: str = None, bucket: str = "boards") -> NormalizedJob:
    return NormalizedJob(
        id=job_id or str(uuid.uuid4()),
        title="Software Engineer",
        company="Acme",
        description="Great job",
        skills=["python", "fastapi"],
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/job",
    )


class _FakeEmbedding:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self._fail:
            raise RuntimeError("embedding model down")
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeVectorStore:
    def __init__(self) -> None:
        # key: job_id -> (vector, metadata)
        self.store: dict[str, tuple[list[float], dict]] = {}

    async def upsert(self, id: str, embedding: list[float], metadata: dict) -> None:
        self.store[id] = (embedding, metadata)

    async def delete(self, ids: list[str]) -> None:
        for id_ in ids:
            self.store.pop(id_, None)


class _FakeRepo:
    def __init__(self, jobs: list[NormalizedJob] = None) -> None:
        self._jobs = {j.id: j for j in (jobs or [])}

    def list_all(self) -> list[NormalizedJob]:
        return list(self._jobs.values())

    def list_filtered(self, criteria) -> list[NormalizedJob]:
        return [j for j in self._jobs.values() if criteria.matches(j)]


def _make_auth_service() -> AuthService:
    return AuthService(username="admin", password="secret", jwt_secret="test-secret")


def _make_authed_app(backfill_svc: EmbeddingBackfillService) -> FastAPI:
    """App wired with real require_auth + injected backfill service."""
    auth_service = _make_auth_service()

    app = FastAPI()

    # Wire identity so require_auth works
    from hiresense.identity.api.dependencies import get_auth_service

    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_backfill_service] = lambda: backfill_svc
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# T1: Auth gate — 401 without token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_requires_auth() -> None:
    """POST /ingestion/backfill-embeddings must return 401 when no token is sent."""
    boards_repo = _FakeRepo([_job()])
    portals_repo = _FakeRepo([_job()])
    embedding = _FakeEmbedding()
    store = _FakeVectorStore()

    svc = EmbeddingBackfillService(
        boards_repo=boards_repo,
        portals_repo=portals_repo,
        embedding=embedding,
        vector_store=store,
    )
    app = _make_authed_app(svc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/backfill-embeddings")

    # HTTPBearer raises 403 when scheme is wrong, 401 when header is absent entirely
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# T2: Production-path — embed + upsert all jobs from both buckets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_embeds_all_jobs_and_returns_counts() -> None:
    """With a valid token and two jobs per bucket, returns counts > 0 and embed is called."""
    board_job = _job("board-1")
    portal_job = _job("portal-1")

    boards_repo = _FakeRepo([board_job])
    portals_repo = _FakeRepo([portal_job])
    embedding = _FakeEmbedding()
    store = _FakeVectorStore()

    svc = EmbeddingBackfillService(
        boards_repo=boards_repo,
        portals_repo=portals_repo,
        embedding=embedding,
        vector_store=store,
    )
    app = _make_authed_app(svc)
    token = _make_auth_service().login("admin", "secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingestion/backfill-embeddings",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["boards"] == 1
    assert data["portals"] == 1
    assert data["total"] == 2
    # Embed was called (at least once per bucket or in a single batch)
    assert len(embedding.calls) >= 1
    # Both jobs were upserted into the vector store
    assert "board-1" in store.store
    assert "portal-1" in store.store
    # Metadata carries the correct bucket tag
    assert store.store["board-1"][1]["bucket"] == "boards"
    assert store.store["portal-1"][1]["bucket"] == "portals"


# ---------------------------------------------------------------------------
# T3: Idempotency — running twice yields same state, no duplicates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_is_idempotent() -> None:
    """Calling the endpoint twice upserts the same vectors; store size stays the same."""
    job = _job("job-1")
    boards_repo = _FakeRepo([job])
    portals_repo = _FakeRepo([])
    embedding = _FakeEmbedding()
    store = _FakeVectorStore()

    svc = EmbeddingBackfillService(
        boards_repo=boards_repo,
        portals_repo=portals_repo,
        embedding=embedding,
        vector_store=store,
    )
    app = _make_authed_app(svc)
    token = _make_auth_service().login("admin", "secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(2):
            resp = await client.post(
                "/ingestion/backfill-embeddings",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200

    # Only one entry in the store regardless of how many times we called
    assert len(store.store) == 1
    assert "job-1" in store.store


# ---------------------------------------------------------------------------
# T4: Empty corpus — no jobs, counts 0, no crash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_empty_corpus_returns_zero_counts() -> None:
    """Empty repos → counts 0, no error."""
    svc = EmbeddingBackfillService(
        boards_repo=_FakeRepo([]),
        portals_repo=_FakeRepo([]),
        embedding=_FakeEmbedding(),
        vector_store=_FakeVectorStore(),
    )
    app = _make_authed_app(svc)
    token = _make_auth_service().login("admin", "secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingestion/backfill-embeddings",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["boards"] == 0
    assert data["portals"] == 0
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# T5: Unavailable vector store — counts 0, graceful response (no 500)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_no_vector_store_returns_zero_gracefully() -> None:
    """When vector_store is None, endpoint returns counts=0 without crashing."""
    svc = EmbeddingBackfillService(
        boards_repo=_FakeRepo([_job("j1")]),
        portals_repo=_FakeRepo([_job("j2")]),
        embedding=_FakeEmbedding(),
        vector_store=None,  # no pgvector configured
    )
    app = _make_authed_app(svc)
    token = _make_auth_service().login("admin", "secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingestion/backfill-embeddings",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["boards"] == 0
    assert data["portals"] == 0


# ---------------------------------------------------------------------------
# T6: get_backfill_service dependency — resolves from app.state.ingestion
# ---------------------------------------------------------------------------


def test_get_backfill_service_resolves_from_provider() -> None:
    """get_backfill_service must read from request.app.state.ingestion."""
    from fastapi import Request
    from hiresense.ingestion.api.dependencies import get_backfill_service

    fake_svc = object()  # sentinel

    class FakeProvider:
        def get_backfill_service(self):
            return fake_svc

    # Simulate a FastAPI Request pointing to an app with wired state
    app = FastAPI()
    app.state.ingestion = FakeProvider()

    # Build a minimal scope/send/receive for Request construction
    scope = {"type": "http", "app": app, "method": "POST", "path": "/"}
    request = Request(scope)
    result = get_backfill_service(request)
    assert result is fake_svc


def test_get_backfill_service_returns_none_on_bare_app() -> None:
    """get_backfill_service must return None defensively when no ingestion state."""
    from fastapi import Request
    from hiresense.ingestion.api.dependencies import get_backfill_service

    app = FastAPI()
    scope = {"type": "http", "app": app, "method": "POST", "path": "/"}
    request = Request(scope)
    result = get_backfill_service(request)
    assert result is None


# ---------------------------------------------------------------------------
# T7: Closed jobs are NOT embedded (W1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_skips_closed_jobs() -> None:
    """Closed/expired jobs must not be embedded or upserted into the vector store."""
    open_job = NormalizedJob(
        id="open-1",
        title="Open Engineer",
        company="Acme",
        description="Open role",
        skills=["python"],
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/open",
        status="open",
    )
    closed_job = NormalizedJob(
        id="closed-1",
        title="Closed Engineer",
        company="Acme",
        description="Closed role",
        skills=["python"],
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/closed",
        status="closed",
    )

    boards_repo = _FakeRepo([open_job, closed_job])
    portals_repo = _FakeRepo([])
    embedding = _FakeEmbedding()
    store = _FakeVectorStore()

    svc = EmbeddingBackfillService(
        boards_repo=boards_repo,
        portals_repo=portals_repo,
        embedding=embedding,
        vector_store=store,
    )
    result = await svc.run()

    # Only the open job was counted and upserted
    assert result.boards == 1
    assert "open-1" in store.store
    assert "closed-1" not in store.store


# ---------------------------------------------------------------------------
# T8: HTTP 503 when get_backfill_service resolves to None (W2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_returns_503_when_service_unavailable() -> None:
    """POST /ingestion/backfill-embeddings must return 503 when service is None."""
    auth_service = _make_auth_service()
    app = FastAPI()

    from hiresense.identity.api.dependencies import get_auth_service

    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_backfill_service] = lambda: None
    app.include_router(router)

    token = auth_service.login("admin", "secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/ingestion/backfill-embeddings",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 503

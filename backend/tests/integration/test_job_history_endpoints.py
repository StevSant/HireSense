"""Integration tests for the job-history and ingestion-run read endpoints.

Exercises the real FastAPI routes (`GET /ingestion/jobs/{id}/history`,
`GET /ingestion/runs`, `GET /ingestion/runs/{id}`) against a fake in-memory
`JobHistoryPort`, mirroring the pattern in `test_ingestion_to_api_flow.py`:
real router, dependency-overridden collaborators, `httpx.AsyncClient` over
`ASGITransport`.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.identity.api.dependencies import require_auth
from hiresense.ingestion.api import router
from hiresense.ingestion.api.dependencies import get_job_history
from hiresense.ingestion.domain import IngestionRunSummary, JobHistoryEvent, JobHistoryEventType
from hiresense.ingestion.infrastructure import JobHistoryRepository
from hiresense.shared.infrastructure.database import Base


def _event(job_id: str, event: JobHistoryEventType, occurred_at: datetime) -> JobHistoryEvent:
    return JobHistoryEvent(job_id=job_id, event=event, occurred_at=occurred_at)


def _run(run_id: str, started_at: datetime) -> IngestionRunSummary:
    return IngestionRunSummary(
        id=run_id,
        started_at=started_at,
        finished_at=started_at,
        trigger="manual",
        status="completed",
        inserted=1,
    )


class _FakeJobHistoryPort:
    """In-memory stand-in for `JobHistoryPort`'s read methods."""

    def __init__(
        self,
        events_by_job: dict[str, list[JobHistoryEvent]] | None = None,
        events_by_run: dict[str, list[JobHistoryEvent]] | None = None,
        runs: list[IngestionRunSummary] | None = None,
    ) -> None:
        self._events_by_job = events_by_job or {}
        self._events_by_run = events_by_run or {}
        self._runs = runs or []

    def list_events_for_job(self, job_id: str, limit: int) -> list[JobHistoryEvent]:
        return self._events_by_job.get(job_id, [])[:limit]

    def list_events_for_run(self, run_id: str, limit: int) -> list[JobHistoryEvent]:
        return self._events_by_run.get(run_id, [])[:limit]

    def list_runs(self, limit: int, offset: int) -> list[IngestionRunSummary]:
        return self._runs[offset : offset + limit]

    def get_run(self, run_id: str) -> IngestionRunSummary | None:
        for run in self._runs:
            if run.id == run_id:
                return run
        return None


class _RealParsingJobHistoryPort(_FakeJobHistoryPort):
    """Delegates run lookups to the real repository, so the route is exercised
    against the same id parsing production uses."""

    def __init__(self) -> None:
        super().__init__()
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self._repo = JobHistoryRepository(session_factory=sessionmaker(bind=engine))

    def list_events_for_run(self, run_id: str, limit: int) -> list[JobHistoryEvent]:
        return self._repo.list_events_for_run(run_id, limit)

    def get_run(self, run_id: str) -> IngestionRunSummary | None:
        return self._repo.get_run(run_id)


def _build_app(history: object | None) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_job_history] = lambda: history
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_job_history_returns_events_newest_first() -> None:
    newest = _event(
        "job-1", JobHistoryEventType.UPDATED, datetime(2026, 8, 19, tzinfo=timezone.utc)
    )
    oldest = _event(
        "job-1", JobHistoryEventType.INSERTED, datetime(2026, 8, 18, tzinfo=timezone.utc)
    )
    history = _FakeJobHistoryPort(events_by_job={"job-1": [newest, oldest]})
    app = _build_app(history)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs/job-1/history")

    assert resp.status_code == 200
    body = resp.json()
    assert [e["event"] for e in body["events"]] == ["updated", "inserted"]


@pytest.mark.asyncio
async def test_job_history_for_an_unknown_job_returns_an_empty_list() -> None:
    history = _FakeJobHistoryPort()
    app = _build_app(history)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs/unknown-job/history")

    assert resp.status_code == 200
    assert resp.json() == {"events": []}


@pytest.mark.asyncio
async def test_job_history_respects_the_limit_parameter() -> None:
    events = [
        _event("job-1", JobHistoryEventType.UPDATED, datetime(2026, 8, day, tzinfo=timezone.utc))
        for day in range(1, 6)
    ]
    history = _FakeJobHistoryPort(events_by_job={"job-1": events})
    app = _build_app(history)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs/job-1/history", params={"limit": 2})

    assert resp.status_code == 200
    assert len(resp.json()["events"]) == 2


@pytest.mark.asyncio
async def test_runs_list_returns_newest_first_with_counts() -> None:
    run_a = _run("run-a", datetime(2026, 8, 18, tzinfo=timezone.utc))
    run_b = _run("run-b", datetime(2026, 8, 19, tzinfo=timezone.utc))
    history = _FakeJobHistoryPort(runs=[run_b, run_a])
    app = _build_app(history)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/runs")

    assert resp.status_code == 200
    body = resp.json()
    assert [r["id"] for r in body["runs"]] == ["run-b", "run-a"]
    assert body["runs"][0]["inserted"] == 1


@pytest.mark.asyncio
async def test_run_detail_returns_the_run_and_its_events() -> None:
    run = _run("run-a", datetime(2026, 8, 18, tzinfo=timezone.utc))
    event = _event(
        "job-1", JobHistoryEventType.INSERTED, datetime(2026, 8, 18, tzinfo=timezone.utc)
    )
    history = _FakeJobHistoryPort(runs=[run], events_by_run={"run-a": [event]})
    app = _build_app(history)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/runs/run-a")

    assert resp.status_code == 200
    body = resp.json()
    assert body["run"]["id"] == "run-a"
    assert len(body["events"]) == 1
    assert body["events"][0]["job_id"] == "job-1"


@pytest.mark.asyncio
async def test_run_detail_for_an_unknown_id_returns_404() -> None:
    history = _FakeJobHistoryPort()
    app = _build_app(history)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/runs/unknown-run")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_detail_for_a_malformed_id_returns_404_not_500() -> None:
    """A stale bookmark is a client mistake, not a server error."""
    app = _build_app(_RealParsingJobHistoryPort())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/runs/not-a-uuid")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_all_three_endpoints_require_auth() -> None:
    app = FastAPI()
    app.dependency_overrides[get_job_history] = lambda: _FakeJobHistoryPort()
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        history_resp = await client.get("/ingestion/jobs/job-1/history")
        runs_resp = await client.get("/ingestion/runs")
        run_detail_resp = await client.get("/ingestion/runs/run-a")

    assert history_resp.status_code == 401
    assert runs_resp.status_code == 401
    assert run_detail_resp.status_code == 401


@pytest.mark.asyncio
async def test_endpoints_return_503_when_no_history_store_is_wired() -> None:
    app = _build_app(None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        history_resp = await client.get("/ingestion/jobs/job-1/history")
        runs_resp = await client.get("/ingestion/runs")
        run_detail_resp = await client.get("/ingestion/runs/run-a")

    assert history_resp.status_code == 503
    assert runs_resp.status_code == 503
    assert run_detail_resp.status_code == 503

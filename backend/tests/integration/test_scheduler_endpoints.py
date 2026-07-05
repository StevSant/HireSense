import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.identity.api.dependencies import require_admin, require_auth
from hiresense.infrastructure.database import Base
from hiresense.scheduler.api import router as scheduler_router
from hiresense.scheduler.api.dependencies import get_scheduler_provider
from hiresense.scheduler.api.provider import SchedulerProvider
from hiresense.scheduler.domain import JobDefinition, JobRunner
from hiresense.scheduler.infrastructure import (
    JobRunOrm,  # noqa: F401
    JobRunRepositoryImpl,
    JobToggleOrm,  # noqa: F401
    JobToggleRepositoryImpl,
)


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class _FakeRunner:
    """Stands in for ApschedulerRunner — no real APScheduler in tests."""

    def __init__(self, job_runner):
        self._job_runner = job_runner

    def next_run_at(self, name):
        return None

    async def trigger_now(self, name):
        return await self._job_runner.run(name)


def _build_app():
    factory = _factory()
    run_repo = JobRunRepositoryImpl(session_factory=factory, retention_days=30)
    toggle_repo = JobToggleRepositoryImpl(session_factory=factory)

    async def fetch():
        return [1, 2, 3]

    defs = [
        JobDefinition(
            name="ingestion_fetch",
            run=fetch,
            cron="0 */6 * * *",
            interval_hours=None,
            count_items=len,
        ),
    ]
    job_runner = JobRunner(definitions=defs, run_repo=run_repo, toggle_repo=toggle_repo)
    provider = SchedulerProvider(
        definitions=defs,
        runner=_FakeRunner(job_runner),
        run_repo=run_repo,
        toggle_repo=toggle_repo,
    )

    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "u"
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    app.dependency_overrides[get_scheduler_provider] = lambda: provider
    app.include_router(scheduler_router)
    return app


@pytest.mark.asyncio
async def test_list_jobs_returns_definitions():
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/scheduler/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["name"] == "ingestion_fetch"
    assert body[0]["enabled"] is True


@pytest.mark.asyncio
async def test_run_now_then_toggle_then_runs_history():
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        run = await client.post("/scheduler/jobs/ingestion_fetch/run-now")
        assert run.status_code == 200
        assert run.json()["status"] == "success"
        assert run.json()["items_affected"] == 3

        runs = await client.get("/scheduler/jobs/ingestion_fetch/runs")
        assert len(runs.json()) == 1

        toggled = await client.post(
            "/scheduler/jobs/ingestion_fetch/toggle", json={"enabled": False}
        )
        assert toggled.status_code == 200
        assert toggled.json()["enabled"] is False

        # Disabled job records a skipped run.
        again = await client.post("/scheduler/jobs/ingestion_fetch/run-now")
        assert again.json()["status"] == "skipped"

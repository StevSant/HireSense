import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.bootstrap.scheduler import build_scheduler
from hiresense.infrastructure.database import Base
from hiresense.scheduler.infrastructure import JobRunOrm, JobToggleOrm  # noqa: F401


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class _Settings:
    ingestion_schedule = "0 */6 * * *"
    job_revalidation_interval_hours = 24
    autohunt_schedule = "0 9 * * *"
    outreach_followup_schedule = "0 10 * * *"
    autopilot_pipeline_schedule = "0 10 * * *"
    scheduler_run_retention_days = 30


class _Noop:
    async def run(self):
        return []

    async def sweep(self):
        return []


class _Auto:
    async def run(self):
        return type("D", (), {"job_count": 0})()


class _Out:
    def due_followups(self):
        return []


class _Pipeline:
    async def run(self):
        return type("R", (), {"created": 5})()


def _build(pipeline):
    return build_scheduler(
        settings=_Settings(),
        sync_session_factory=_factory(),
        ingestion_orchestrator=_Noop(),
        revalidation_service=_Noop(),
        autohunt_service=_Auto(),
        outreach_service=_Out(),
        autopilot_pipeline_service=pipeline,
    )


@pytest.mark.asyncio
async def test_autopilot_job_present_when_injected():
    build = _build(_Pipeline())
    names = {v.name for v in build.provider.list_jobs()}
    assert "autopilot_pipeline" in names
    run = await build.provider.run_now("autopilot_pipeline")
    assert run.items_affected == 5


def test_autopilot_job_absent_by_default():
    build = _build(None)
    names = {v.name for v in build.provider.list_jobs()}
    assert "autopilot_pipeline" not in names

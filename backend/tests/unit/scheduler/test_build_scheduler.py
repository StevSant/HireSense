import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.bootstrap.scheduler import build_scheduler
from hiresense.infrastructure.database import Base
from hiresense.scheduler.infrastructure import JobRunOrm, JobToggleOrm  # noqa: F401


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class _Settings:
    ingestion_schedule = "0 */6 * * *"
    job_revalidation_interval_hours = 24
    autohunt_schedule = "0 9 * * *"
    outreach_followup_schedule = "0 10 * * *"
    scheduler_run_retention_days = 30


class _Orchestrator:
    async def run(self):
        return [1, 2]


class _Revalidation:
    async def sweep(self):
        return ["closed-1"]


class _Autohunt:
    async def run(self):
        return type("D", (), {"job_count": 4})()


class _Outreach:
    def due_followups(self):
        return [1, 2, 3]


def test_build_scheduler_registers_all_four_jobs():
    build = build_scheduler(
        settings=_Settings(),
        sync_session_factory=_factory(),
        ingestion_orchestrator=_Orchestrator(),
        revalidation_service=_Revalidation(),
        autohunt_service=_Autohunt(),
        outreach_service=_Outreach(),
    )
    names = {v.name for v in build.provider.list_jobs()}
    assert names == {"ingestion_fetch", "revalidation_sweep", "autohunt_digest", "outreach_followups"}


@pytest.mark.asyncio
async def test_built_autohunt_job_counts_digest_entries():
    build = build_scheduler(
        settings=_Settings(),
        sync_session_factory=_factory(),
        ingestion_orchestrator=_Orchestrator(),
        revalidation_service=_Revalidation(),
        autohunt_service=_Autohunt(),
        outreach_service=_Outreach(),
    )
    run = await build.provider.run_now("autohunt_digest")
    assert run.items_affected == 4

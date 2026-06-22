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
    inbox_scan_schedule = "0 */2 * * *"
    scheduler_run_retention_days = 30


class _Svc:
    async def run(self): return 4


def _noop():
    class _N:
        async def run(self): return []
        async def sweep(self): return []
    return _N()


@pytest.mark.asyncio
async def test_inbox_scan_job_present_when_service_injected():
    class _Auto:
        async def run(self): return type("D", (), {"job_count": 0})()
    class _Out:
        def due_followups(self): return []
    build = build_scheduler(
        settings=_Settings(), sync_session_factory=_factory(),
        ingestion_orchestrator=_noop(), revalidation_service=_noop(),
        autohunt_service=_Auto(), outreach_service=_Out(),
        inbox_processing_service=_Svc(),
    )
    names = {v.name for v in build.provider.list_jobs()}
    assert "inbox_scan" in names
    run = await build.provider.run_now("inbox_scan")
    assert run.items_affected == 4


def test_inbox_scan_absent_by_default():
    class _Auto:
        async def run(self): return type("D", (), {"job_count": 0})()
    class _Out:
        def due_followups(self): return []
    build = build_scheduler(
        settings=_Settings(), sync_session_factory=_factory(),
        ingestion_orchestrator=_noop(), revalidation_service=_noop(),
        autohunt_service=_Auto(), outreach_service=_Out(),
    )
    names = {v.name for v in build.provider.list_jobs()}
    assert "inbox_scan" not in names

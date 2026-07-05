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
    scheduler_run_retention_days = 30


class _Orchestrator:
    async def run(self):
        return [1, 2]


class _Revalidation:
    async def sweep(self):
        return []


class _Outreach:
    def due_followups(self):
        return []


class _Autohunt:
    def __init__(self, job_count):
        self._jc = job_count

    async def run(self):
        return type("D", (), {"job_count": self._jc})()


class _Notifier:
    def __init__(self):
        self.matches = []

    async def notify_new_matches(self, digest):
        self.matches.append(digest)

    async def notify_job_failure(self, job_name, detail): ...


def _build(autohunt, notifier):
    return build_scheduler(
        settings=_Settings(),
        sync_session_factory=_factory(),
        ingestion_orchestrator=_Orchestrator(),
        revalidation_service=_Revalidation(),
        autohunt_service=autohunt,
        outreach_service=_Outreach(),
        notification_service=notifier,
    )


@pytest.mark.asyncio
async def test_autohunt_notifies_when_matches():
    notifier = _Notifier()
    build = _build(_Autohunt(job_count=3), notifier)
    run = await build.provider.run_now("autohunt_digest")
    assert run.status.value == "success"
    assert run.items_affected == 3
    assert len(notifier.matches) == 1


@pytest.mark.asyncio
async def test_autohunt_silent_when_no_matches():
    notifier = _Notifier()
    build = _build(_Autohunt(job_count=0), notifier)
    await build.provider.run_now("autohunt_digest")
    assert notifier.matches == []

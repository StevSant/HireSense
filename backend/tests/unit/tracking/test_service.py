from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

import pytest

from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.domain.services import TrackingService


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeJob:
    def __init__(self, id: str, title: str, company: str, url: str | None = None) -> None:
        self.id = id
        self.title = title
        self.company = company
        self.url = url


class FakeIngestionOrchestrator:
    def __init__(self, jobs: dict[str, FakeJob] | None = None) -> None:
        self._jobs: dict[str, FakeJob] = jobs or {}

    def get_job_by_id(self, job_id: str) -> FakeJob | None:
        return self._jobs.get(job_id)


class FakeEventBus:
    def __init__(self) -> None:
        self.published: list = []

    async def publish(self, event) -> None:
        self.published.append(event)

    def subscribe(self, event_type, handler) -> None:
        pass


class FakeRepository:
    def __init__(self) -> None:
        self._store: dict[uuid_mod.UUID, TrackedApplication] = {}

    def create(self, app: TrackedApplication) -> TrackedApplication:
        if app.id is None:
            app.id = uuid_mod.uuid4()
        now = datetime.now(timezone.utc)
        if app.created_at is None:
            app.created_at = now
        if app.updated_at is None:
            app.updated_at = now
        self._store[app.id] = app
        return app

    def get_by_id(self, id: uuid_mod.UUID) -> TrackedApplication | None:
        return self._store.get(id)

    def get_by_job_id(self, job_id: uuid_mod.UUID) -> TrackedApplication | None:
        for app in self._store.values():
            if app.job_id == job_id:
                return app
        return None

    def list_all(self, status: ApplicationStatus | None = None) -> list[TrackedApplication]:
        apps = list(self._store.values())
        if status is not None:
            apps = [a for a in apps if a.status == status.value]
        return apps

    def save(self, app: TrackedApplication) -> TrackedApplication:
        app.updated_at = datetime.now(timezone.utc)
        self._store[app.id] = app
        return app

    def delete(self, id: uuid_mod.UUID) -> bool:
        if id in self._store:
            del self._store[id]
            return True
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_service(
    repo: FakeRepository | None = None,
    orchestrator: FakeIngestionOrchestrator | None = None,
    event_bus: FakeEventBus | None = None,
) -> TrackingService:
    return TrackingService(
        repository=repo or FakeRepository(),
        ingestion_orchestrator=orchestrator or FakeIngestionOrchestrator(),
        event_bus=event_bus or FakeEventBus(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_track_manual_job() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)

    app = svc.track_job(title="Backend Engineer", company="Acme Corp", url="https://acme.io/jobs/1")

    assert app.id is not None
    assert app.title == "Backend Engineer"
    assert app.company == "Acme Corp"
    assert app.url == "https://acme.io/jobs/1"
    assert app.status == ApplicationStatus.SAVED.value
    assert app.job_id is None


def test_track_from_ingestion() -> None:
    job_id = str(uuid_mod.uuid4())
    job = FakeJob(id=job_id, title="ML Engineer", company="DeepMind", url="https://deepmind.com/jobs/1")
    repo = FakeRepository()
    orchestrator = FakeIngestionOrchestrator(jobs={job_id: job})
    svc = make_service(repo=repo, orchestrator=orchestrator)

    app = svc.track_from_ingestion(job_id)

    assert app.job_id == uuid_mod.UUID(job_id)
    assert app.title == "ML Engineer"
    assert app.company == "DeepMind"
    assert app.url == "https://deepmind.com/jobs/1"
    assert app.status == ApplicationStatus.SAVED.value


def test_track_from_ingestion_not_found() -> None:
    svc = make_service()
    with pytest.raises(ValueError, match="not found"):
        svc.track_from_ingestion(str(uuid_mod.uuid4()))


def test_track_from_ingestion_already_tracked() -> None:
    job_id = str(uuid_mod.uuid4())
    job = FakeJob(id=job_id, title="SRE", company="Google")
    repo = FakeRepository()
    orchestrator = FakeIngestionOrchestrator(jobs={job_id: job})
    svc = make_service(repo=repo, orchestrator=orchestrator)

    svc.track_from_ingestion(job_id)

    with pytest.raises(ValueError, match="already tracked"):
        svc.track_from_ingestion(job_id)


def test_get_application() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    created = svc.track_job(title="DevOps", company="Stripe")

    fetched = svc.get(created.id)

    assert fetched.id == created.id
    assert fetched.title == "DevOps"


def test_get_application_not_found() -> None:
    svc = make_service()
    with pytest.raises(ValueError, match="not found"):
        svc.get(uuid_mod.uuid4())


def test_list_applications() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    svc.track_job(title="Job A", company="Co A")
    svc.track_job(title="Job B", company="Co B")

    apps = svc.list()

    assert len(apps) == 2


async def test_list_filter_by_status() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    app_a = svc.track_job(title="Job A", company="Co A")
    svc.track_job(title="Job B", company="Co B")

    await svc.update_status(app_a.id, ApplicationStatus.APPLIED)

    saved = svc.list(status=ApplicationStatus.SAVED)
    applied = svc.list(status=ApplicationStatus.APPLIED)

    assert len(saved) == 1
    assert len(applied) == 1
    assert applied[0].id == app_a.id


async def test_update_status() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    app = svc.track_job(title="Data Scientist", company="OpenAI")

    updated = await svc.update_status(app.id, ApplicationStatus.INTERVIEWING)

    assert updated.status == ApplicationStatus.INTERVIEWING.value


async def test_update_status_to_applied_sets_applied_at() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    app = svc.track_job(title="Product Manager", company="Meta")
    assert app.applied_at is None

    updated = await svc.update_status(app.id, ApplicationStatus.APPLIED)

    assert updated.applied_at is not None


async def test_update_status_to_applied_does_not_overwrite_applied_at() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    app = svc.track_job(title="Frontend Dev", company="Vercel")

    first = await svc.update_status(app.id, ApplicationStatus.APPLIED)
    original_applied_at = first.applied_at

    # transition to another status then back to APPLIED
    await svc.update_status(app.id, ApplicationStatus.INTERVIEWING)
    second = await svc.update_status(app.id, ApplicationStatus.APPLIED)

    assert second.applied_at == original_applied_at


async def test_update_status_emits_event_on_actual_change() -> None:
    job_id = str(uuid_mod.uuid4())
    job = FakeJob(id=job_id, title="Backend Engineer", company="Acme")
    repo = FakeRepository()
    orchestrator = FakeIngestionOrchestrator(jobs={job_id: job})
    bus = FakeEventBus()
    svc = make_service(repo=repo, orchestrator=orchestrator, event_bus=bus)
    app = svc.track_from_ingestion(job_id)

    await svc.update_status(app.id, ApplicationStatus.APPLIED)

    assert len(bus.published) == 1
    event = bus.published[0]
    assert event.event_type == "tracking.status_changed"
    assert event.status == "applied"
    assert event.job_id == str(uuid_mod.UUID(job_id))


async def test_update_status_no_event_when_status_unchanged() -> None:
    job_id = str(uuid_mod.uuid4())
    job = FakeJob(id=job_id, title="SRE", company="Google")
    repo = FakeRepository()
    orchestrator = FakeIngestionOrchestrator(jobs={job_id: job})
    bus = FakeEventBus()
    svc = make_service(repo=repo, orchestrator=orchestrator, event_bus=bus)
    app = svc.track_from_ingestion(job_id)

    await svc.update_status(app.id, ApplicationStatus.APPLIED)
    bus.published.clear()

    await svc.update_status(app.id, ApplicationStatus.APPLIED)

    assert bus.published == []


async def test_update_status_no_event_when_job_id_none() -> None:
    repo = FakeRepository()
    bus = FakeEventBus()
    svc = make_service(repo=repo, event_bus=bus)
    app = svc.track_job(title="Manual Job", company="NoCorp")
    assert app.job_id is None

    await svc.update_status(app.id, ApplicationStatus.OFFERED)

    assert bus.published == []


def test_update_notes() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    app = svc.track_job(title="QA Engineer", company="Atlassian")

    updated = svc.update_notes(app.id, "Great culture fit")

    assert updated.notes == "Great culture fit"


def test_remove() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    app = svc.track_job(title="Backend Dev", company="Twilio")

    svc.remove(app.id)

    with pytest.raises(ValueError, match="not found"):
        svc.get(app.id)


def test_remove_not_found() -> None:
    svc = make_service()
    with pytest.raises(ValueError, match="not found"):
        svc.remove(uuid_mod.uuid4())

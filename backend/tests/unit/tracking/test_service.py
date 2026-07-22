from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

import pytest

from hiresense.tracking.domain import InvalidStatusTransitionError
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
        self.history: list = []

    def create(self, app: TrackedApplication) -> TrackedApplication:
        if app.id is None:
            app.id = uuid_mod.uuid4()
        now = datetime.now(timezone.utc)
        if app.created_at is None:
            app.created_at = now
        if app.updated_at is None:
            app.updated_at = now
        self._store[app.id] = app
        self.history.append((None, app.status))
        return app

    def get_by_id(self, id: uuid_mod.UUID) -> TrackedApplication | None:
        return self._store.get(id)

    def get_by_job_id(self, job_id: uuid_mod.UUID) -> TrackedApplication | None:
        for app in self._store.values():
            if app.job_id == job_id:
                return app
        return None

    def list_all(
        self,
        status: ApplicationStatus | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackedApplication]:
        apps = list(self._store.values())
        if status is not None:
            apps = [a for a in apps if a.status == status.value]
        if offset:
            apps = apps[offset:]
        if limit is not None:
            apps = apps[:limit]
        return apps

    def count_all(self, status: ApplicationStatus | None = None) -> int:
        apps = list(self._store.values())
        if status is not None:
            apps = [a for a in apps if a.status == status.value]
        return len(apps)

    def save(self, app: TrackedApplication) -> TrackedApplication:
        app.updated_at = datetime.now(timezone.utc)
        self._store[app.id] = app
        return app

    def save_with_history(self, application, *, from_status, to_status):
        self.history.append((from_status, to_status))
        return self.save(application)

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


def _make_app(
    job_id: uuid_mod.UUID | None = None,
    status: str = ApplicationStatus.SAVED.value,
) -> TrackedApplication:
    return TrackedApplication(
        job_id=job_id,
        title="Engineer",
        company="Acme",
        status=status,
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


def test_track_manual_job_with_listing_metadata() -> None:
    posted = datetime(2026, 7, 1, tzinfo=timezone.utc)
    svc = make_service()

    app = svc.track_job(
        title="Backend Engineer",
        company="Acme Corp",
        location="Quito",
        remote_modality="remote",
        salary_range="USD 1,500-2,000/mo",
        source="Referral",
        posted_date=posted,
    )

    assert app.location == "Quito"
    assert app.remote_modality == "remote"
    assert app.salary_range == "USD 1,500-2,000/mo"
    assert app.source == "Referral"
    assert app.posted_date == posted


def test_track_from_ingestion() -> None:
    job_id = str(uuid_mod.uuid4())
    job = FakeJob(
        id=job_id, title="ML Engineer", company="DeepMind", url="https://deepmind.com/jobs/1"
    )
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


async def test_update_status_rejects_invalid_transition() -> None:
    repo = FakeRepository()
    bus = FakeEventBus()
    svc = make_service(repo=repo, event_bus=bus)
    app = svc.track_job(title="Data Scientist", company="OpenAI")
    await svc.update_status(app.id, ApplicationStatus.REJECTED)

    # REJECTED is terminal — reviving it back to SAVED must be refused, and the
    # application must be left untouched (no mutation, no event).
    with pytest.raises(InvalidStatusTransitionError):
        await svc.update_status(app.id, ApplicationStatus.SAVED)

    assert svc.get(app.id).status == ApplicationStatus.REJECTED.value


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


@pytest.mark.asyncio
async def test_update_status_records_transition_on_change():
    bus = FakeEventBus()
    repo = FakeRepository()
    created = repo.create(_make_app(job_id=uuid_mod.uuid4(), status=ApplicationStatus.SAVED.value))
    service = TrackingService(
        repository=repo, ingestion_orchestrator=FakeIngestionOrchestrator(), event_bus=bus
    )
    await service.update_status(created.id, ApplicationStatus.APPLIED)
    assert repo.history[-1] == ("saved", "applied")


@pytest.mark.asyncio
async def test_update_status_no_transition_when_unchanged():
    bus = FakeEventBus()
    repo = FakeRepository()
    created = repo.create(_make_app(status=ApplicationStatus.APPLIED.value))
    before = len(repo.history)
    service = TrackingService(
        repository=repo, ingestion_orchestrator=FakeIngestionOrchestrator(), event_bus=bus
    )
    await service.update_status(created.id, ApplicationStatus.APPLIED)
    assert len(repo.history) == before


def test_update_notes() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    app = svc.track_job(title="QA Engineer", company="Atlassian")

    updated = svc.update_notes(app.id, "Great culture fit")

    assert updated.notes == "Great culture fit"


def test_update_details_preserves_omitted_fields_and_clears_explicit_null() -> None:
    svc = make_service()
    app = svc.track_job(
        title="QA Engineer",
        company="Atlassian",
        location="Quito",
        remote_modality="hybrid",
        salary_range="USD 1,500/mo",
    )

    updated = svc.update_details(
        app.id,
        {"title": "Senior QA Engineer", "location": None, "source": "Referral"},
    )

    assert updated.title == "Senior QA Engineer"
    assert updated.location is None
    assert updated.source == "Referral"
    assert updated.remote_modality == "hybrid"
    assert updated.salary_range == "USD 1,500/mo"


@pytest.mark.asyncio
async def test_combined_update_commits_status_and_details_once_with_history() -> None:
    class RecordingRepository(FakeRepository):
        def __init__(self) -> None:
            super().__init__()
            self.save_calls = 0
            self.history_save_calls: list[tuple[TrackedApplication, str | None, str]] = []

        def save(self, app: TrackedApplication) -> TrackedApplication:
            self.save_calls += 1
            return super().save(app)

        def save_with_history(self, application, *, from_status, to_status):
            self.history_save_calls.append(
                (application.model_copy(deep=True), from_status, to_status)
            )
            self._store[application.id] = application
            return application

    repo = RecordingRepository()
    service = make_service(repo=repo)
    app = service.track_job(title="Engineer", company="Acme")

    updated = await service.update_application(
        app.id,
        status=ApplicationStatus.APPLIED,
        changes={"title": "Senior Engineer", "source": "Referral"},
    )

    assert updated.status == "applied"
    assert updated.title == "Senior Engineer"
    assert updated.source == "Referral"
    assert repo.save_calls == 0
    assert len(repo.history_save_calls) == 1
    committed, from_status, to_status = repo.history_save_calls[0]
    assert committed.title == "Senior Engineer"
    assert committed.source == "Referral"
    assert (from_status, to_status) == ("saved", "applied")


@pytest.mark.asyncio
async def test_repository_failure_does_not_publish_status_event() -> None:
    class FailingRepository(FakeRepository):
        def save_with_history(self, application, *, from_status, to_status):
            raise RuntimeError("commit failed")

    job_id = uuid_mod.uuid4()
    repo = FailingRepository()
    app = repo.create(_make_app(job_id=job_id))
    bus = FakeEventBus()
    service = make_service(repo=repo, event_bus=bus)

    with pytest.raises(RuntimeError, match="commit failed"):
        await service.update_application(
            app.id,
            status=ApplicationStatus.APPLIED,
            changes={"title": "Senior Engineer"},
        )

    assert bus.published == []
    assert repo.get_by_id(app.id).status == "saved"
    assert repo.get_by_id(app.id).title == "Engineer"


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

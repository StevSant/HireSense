from __future__ import annotations

import uuid

import pytest

from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.models import ApplicationJobSnapshot, JobSnapshotSource


class FakeNormalizedJob:
    def __init__(
        self,
        id_: str,
        title: str,
        company: str,
        description: str,
        skills: list[str],
        url: str | None = None,
    ) -> None:
        self.id = id_
        self.title = title
        self.company = company
        self.description = description
        self.skills = skills
        self.url = url


class FakeIngestionOrchestrator:
    def __init__(self, jobs: dict[str, FakeNormalizedJob] | None = None) -> None:
        self._jobs = jobs or {}

    def get_job_by_id(self, job_id: str):
        return self._jobs.get(job_id)


class FakeTrackingService:
    def __init__(self) -> None:
        self.tracked: dict[uuid.UUID, object] = {}

    def track_from_ingestion(self, job_id: str):
        from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication

        job_uuid = uuid.UUID(job_id)
        app = TrackedApplication(
            id=uuid.uuid4(),
            job_id=job_uuid,
            title="Software Engineer",
            company="Fieldguide",
            status=ApplicationStatus.SAVED.value,
        )
        self.tracked[app.id] = app
        return app

    def track_job(self, title: str, company: str, url=None, notes=None):
        from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication

        app = TrackedApplication(
            id=uuid.uuid4(),
            title=title,
            company=company,
            url=url,
            notes=notes,
            status=ApplicationStatus.SAVED.value,
        )
        self.tracked[app.id] = app
        return app

    def get(self, id_):
        if id_ not in self.tracked:
            raise ValueError(f"Application {id_} not found")
        return self.tracked[id_]

    def list(self, status=None):
        return list(self.tracked.values())

    def remove(self, id_):
        if id_ not in self.tracked:
            raise ValueError(f"Application {id_} not found")
        del self.tracked[id_]


class FakeRepo:
    def __init__(self) -> None:
        self.snapshots: dict[uuid.UUID, ApplicationJobSnapshot] = {}

    def create_snapshot(self, snap):
        snap.id = snap.id or uuid.uuid4()
        self.snapshots[snap.application_id] = snap
        return snap

    def get_snapshot(self, application_id):
        return self.snapshots.get(application_id)

    def save_snapshot(self, snap):
        self.snapshots[snap.application_id] = snap
        return snap

    def list_matches(self, application_id):
        return []

    def get_latest_match(self, application_id):
        return None

    def list_optimizations(self, application_id):
        return []

    def get_latest_optimization(self, application_id):
        return None

    def list_interview_preps(self, application_id):
        return []

    def get_latest_interview_prep(self, application_id):
        return None

    def get_latest_cover_letter(self, application_id):
        return None

    def list_cover_letters(self, application_id):
        return []


class FakeSkillExtractor:
    def __init__(self, skills: list[str]) -> None:
        self.skills = skills
        self.called_with: str | None = None

    async def extract(self, description: str) -> list[str]:
        self.called_with = description
        return self.skills


@pytest.mark.asyncio
async def test_create_from_ingested_job_copies_skills_without_llm() -> None:
    job_id = str(uuid.uuid4())
    ingestion = FakeIngestionOrchestrator(
        {
            job_id: FakeNormalizedJob(
                job_id, "Software Engineer", "Fieldguide", "Build cool stuff", ["python", "fastapi"]
            )
        }
    )
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=["should_not_be_called"])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )

    agg = await service.create_from_ingested(job_id)

    assert agg.job_snapshot is not None
    assert agg.job_snapshot.required_skills == ["python", "fastapi"]
    assert agg.job_snapshot.source == JobSnapshotSource.INGESTED.value
    assert extractor.called_with is None  # LLM not called for ingested jobs


@pytest.mark.asyncio
async def test_create_from_ingested_falls_back_to_llm_when_skills_empty() -> None:
    """LinkedIn/HN Hiring ingest jobs with skills=[] — the fallback runs the
    extractor against the description so the snapshot is still useful."""
    job_id = str(uuid.uuid4())
    ingestion = FakeIngestionOrchestrator(
        {
            job_id: FakeNormalizedJob(
                job_id,
                "SRE",
                "Acme",
                "Hiring SRE for Kubernetes and Terraform.",
                [],  # empty skills
            )
        }
    )
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=["kubernetes", "terraform"])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )

    agg = await service.create_from_ingested(job_id)

    assert agg.job_snapshot is not None
    assert agg.job_snapshot.required_skills == ["kubernetes", "terraform"]
    assert agg.job_snapshot.source == JobSnapshotSource.LLM_EXTRACTED.value
    assert extractor.called_with == "Hiring SRE for Kubernetes and Terraform."


@pytest.mark.asyncio
async def test_create_from_ingested_skips_llm_when_description_empty() -> None:
    """If both skills and description are empty, the snapshot just stays INGESTED with []."""
    job_id = str(uuid.uuid4())
    ingestion = FakeIngestionOrchestrator({job_id: FakeNormalizedJob(job_id, "X", "Y", "", [])})
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=["should_not_run"])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )

    agg = await service.create_from_ingested(job_id)

    assert agg.job_snapshot is not None
    assert agg.job_snapshot.required_skills == []
    assert agg.job_snapshot.source == JobSnapshotSource.INGESTED.value
    assert extractor.called_with is None


@pytest.mark.asyncio
async def test_create_from_manual_calls_llm_extractor() -> None:
    ingestion = FakeIngestionOrchestrator()
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=["python", "kubernetes"])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )

    agg = await service.create_from_manual(
        title="SRE", company="Acme", description="Run k8s clusters", url=None
    )

    assert agg.job_snapshot is not None
    assert agg.job_snapshot.required_skills == ["python", "kubernetes"]
    assert agg.job_snapshot.source == JobSnapshotSource.LLM_EXTRACTED.value
    assert extractor.called_with == "Run k8s clusters"


@pytest.mark.asyncio
async def test_create_from_manual_with_empty_extraction_uses_manual_source() -> None:
    ingestion = FakeIngestionOrchestrator()
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=[])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )

    agg = await service.create_from_manual(title="X", company="Y", description="job desc", url=None)
    assert agg.job_snapshot is not None
    assert agg.job_snapshot.required_skills == []
    assert agg.job_snapshot.source == JobSnapshotSource.MANUAL.value


@pytest.mark.asyncio
async def test_update_snapshot_in_place() -> None:
    ingestion = FakeIngestionOrchestrator()
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=[])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )

    agg = await service.create_from_manual("X", "Y", "desc", url=None)
    updated = service.update_snapshot(agg.id, description="new desc", required_skills=["docker"])
    assert updated.job_snapshot is not None
    assert updated.job_snapshot.description == "new desc"
    assert updated.job_snapshot.required_skills == ["docker"]


@pytest.mark.asyncio
async def test_regenerate_skills_calls_extractor() -> None:
    ingestion = FakeIngestionOrchestrator()
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=["aws"])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )
    agg = await service.create_from_manual("X", "Y", "desc", url=None)
    extractor.skills = ["docker", "k8s"]  # change return
    extractor.called_with = None

    refreshed = await service.regenerate_skills(agg.id)
    assert refreshed.job_snapshot is not None
    assert refreshed.job_snapshot.required_skills == ["docker", "k8s"]
    assert extractor.called_with == "desc"

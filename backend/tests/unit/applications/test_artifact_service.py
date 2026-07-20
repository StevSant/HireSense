from __future__ import annotations

import uuid

import pytest

from hiresense.applications.domain.artifact_service import ArtifactService
from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
    JobSnapshotSource,
)


class FakeRepo:
    def __init__(self, snapshot: ApplicationJobSnapshot | None = None) -> None:
        self._snapshot = snapshot
        self.matches: list[ApplicationMatch] = []
        self.opts: list[ApplicationCvOptimization] = []
        self.preps: list[ApplicationInterviewPrep] = []

    def get_snapshot(self, application_id):
        return self._snapshot

    def create_match(self, match):
        match.id = match.id or uuid.uuid4()
        self.matches.append(match)
        return match

    def get_latest_match(self, application_id):
        return self.matches[-1] if self.matches else None

    def get_match(self, match_id):
        return next((m for m in self.matches if m.id == match_id), None)

    def create_optimization(self, opt):
        opt.id = opt.id or uuid.uuid4()
        self.opts.append(opt)
        return opt

    def create_interview_prep(self, prep):
        prep.id = prep.id or uuid.uuid4()
        self.preps.append(prep)
        return prep


class FakeMatchResult:
    def __init__(self) -> None:
        from hiresense.matching.domain.models import ScoreBreakdown

        self.overall_score = 0.75
        self.breakdown = ScoreBreakdown(
            semantic_score=0.8,
            skill_score=0.7,
            experience_score=0.75,
            language_score=0.7,
        )
        self.matched_skills = ["python"]
        self.missing_skills = ["k8s"]
        self.pros = ["good"]
        self.cons = ["short on infra"]
        self.recommendations = ["learn k8s"]


class FakeMatchingOrchestrator:
    def __init__(self) -> None:
        self.last_args: dict | None = None

    async def analyze(
        self, *, job_id, cv_id, job_description, job_skills, cv_summary, cv_skills, **kwargs
    ):
        self.last_args = {
            "job_description": job_description,
            "job_skills": job_skills,
            "cv_summary": cv_summary,
            "cv_skills": cv_skills,
            "cv_text": kwargs.get("cv_text"),
        }
        return FakeMatchResult()


class FakeProfile:
    def __init__(self, language: str, summary: str, skills: list[str], raw_tex: str = "") -> None:
        self.language = language
        self.summary = summary
        self.skills = skills
        self.raw_tex = raw_tex


class FakeProfileService:
    def __init__(self, profile: FakeProfile | None) -> None:
        self._profile = profile

    def get_for_language(self, language: str) -> FakeProfile | None:
        return self._profile


class FakeOptimizerResult:
    def __init__(self) -> None:
        self.optimized_tex = "OPT_TEX"
        self.improvement_summary = "tightened skills"
        self.changes = [{"section": "skills", "before": "x", "after": "y"}]


class FakeOptimizer:
    def __init__(self) -> None:
        self.last_args: dict | None = None

    async def optimize(
        self,
        *,
        match_id,
        job_id,
        cv_id,
        original_tex,
        job_description,
        job_skills,
        missing_skills,
        recommendations,
    ):
        self.last_args = {
            "original_tex": original_tex,
            "job_skills": job_skills,
            "missing_skills": missing_skills,
        }
        return FakeOptimizerResult()


class FakePrepResult:
    def __init__(self) -> None:
        self.job_title = "X"
        self.company = "Y"
        self.matched_stories = []
        self.competencies_to_probe = ["leadership"]
        self.technical_topics = ["k8s"]
        self.negotiation_points = ["remote"]


class FakeInterviewPrepService:
    def __init__(self) -> None:
        self.last_job: dict | None = None

    async def prepare(self, job: dict):
        self.last_job = job
        return FakePrepResult()


@pytest.mark.asyncio
async def test_generate_match_uses_snapshot_and_profile() -> None:
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="job desc",
        required_skills=["python", "k8s"],
        source=JobSnapshotSource.MANUAL.value,
    )
    repo = FakeRepo(snapshot=snap)
    matching = FakeMatchingOrchestrator()
    profiles = FakeProfileService(FakeProfile("en", "I am a senior engineer.", ["python"]))

    service = ArtifactService(
        repository=repo,
        matching_orchestrator=matching,
        cv_optimizer=None,
        interview_prep_service=None,
        profile_service=profiles,
    )

    result = await service.generate_match(app_id, cv_language="en")
    assert result.overall_score == 0.75
    assert result.matched_skills == ["python"]
    assert matching.last_args["job_description"] == "job desc"
    assert matching.last_args["job_skills"] == ["python", "k8s"]
    assert matching.last_args["cv_skills"] == ["python"]


@pytest.mark.asyncio
async def test_generate_match_skips_fallback_when_result_has_skill_verdict(monkeypatch) -> None:
    """When analyze() already returns matched + missing skills, the SkillMatcher
    fallback (normalization + set math) must not run at all."""
    import hiresense.applications.domain.artifact_service as artifact_module

    calls = {"instantiated": 0}

    class SpyMatcher:
        def __init__(self) -> None:
            calls["instantiated"] += 1

        def match(self, *args, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("SkillMatcher.match should not be called")

    monkeypatch.setattr(artifact_module, "SkillMatcher", SpyMatcher)

    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="job desc",
        required_skills=["python", "k8s"],
        source=JobSnapshotSource.MANUAL.value,
    )
    service = ArtifactService(
        repository=FakeRepo(snapshot=snap),
        matching_orchestrator=FakeMatchingOrchestrator(),  # returns matched+missing
        cv_optimizer=None,
        interview_prep_service=None,
        profile_service=FakeProfileService(FakeProfile("en", "s", ["python"])),
    )

    result = await service.generate_match(app_id, cv_language="en")

    assert calls["instantiated"] == 0
    assert result.matched_skills == ["python"]
    assert result.missing_skills == ["k8s"]


@pytest.mark.asyncio
async def test_generate_match_runs_fallback_when_verdict_missing(monkeypatch) -> None:
    """When analyze() returns no skill verdict, the fallback is computed once."""
    import hiresense.applications.domain.artifact_service as artifact_module

    calls = {"instantiated": 0}

    class SpyResult:
        matched = ["python"]
        missing = ["k8s"]

    class SpyMatcher:
        def __init__(self) -> None:
            calls["instantiated"] += 1

        def match(self, cv_skills, job_skills, evidence_text=""):
            return SpyResult()

    class EmptyVerdictOrchestrator:
        async def analyze(self, **kwargs):
            r = FakeMatchResult()
            r.matched_skills = []
            r.missing_skills = []
            return r

    monkeypatch.setattr(artifact_module, "SkillMatcher", SpyMatcher)

    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="job desc",
        required_skills=["python", "k8s"],
        source=JobSnapshotSource.MANUAL.value,
    )
    service = ArtifactService(
        repository=FakeRepo(snapshot=snap),
        matching_orchestrator=EmptyVerdictOrchestrator(),
        cv_optimizer=None,
        interview_prep_service=None,
        profile_service=FakeProfileService(FakeProfile("en", "s", ["python"])),
    )

    result = await service.generate_match(app_id, cv_language="en")

    assert calls["instantiated"] == 1
    assert result.matched_skills == ["python"]
    assert result.missing_skills == ["k8s"]


@pytest.mark.asyncio
async def test_generate_match_passes_cv_text_as_evidence() -> None:
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="job desc",
        required_skills=["python"],
        source=JobSnapshotSource.MANUAL.value,
    )
    repo = FakeRepo(snapshot=snap)
    matching = FakeMatchingOrchestrator()
    profiles = FakeProfileService(
        FakeProfile(
            "en",
            "Senior engineer.",
            ["python"],
            raw_tex=r"\section{Experience} Built distributed systems with Kafka.",
        )
    )

    service = ArtifactService(
        repository=repo,
        matching_orchestrator=matching,
        cv_optimizer=None,
        interview_prep_service=None,
        profile_service=profiles,
    )

    await service.generate_match(app_id, cv_language="en")
    assert "distributed systems" in matching.last_args["cv_text"]


@pytest.mark.asyncio
async def test_generate_match_raises_when_no_snapshot() -> None:
    repo = FakeRepo(snapshot=None)
    service = ArtifactService(
        repository=repo,
        matching_orchestrator=FakeMatchingOrchestrator(),
        cv_optimizer=None,
        interview_prep_service=None,
        profile_service=FakeProfileService(FakeProfile("en", "s", [])),
    )
    with pytest.raises(ValueError, match="Snapshot"):
        await service.generate_match(uuid.uuid4(), cv_language="en")


@pytest.mark.asyncio
async def test_generate_match_raises_when_no_profile() -> None:
    snap = ApplicationJobSnapshot(
        application_id=uuid.uuid4(),
        description="d",
        required_skills=[],
        source="manual",
    )
    repo = FakeRepo(snapshot=snap)
    service = ArtifactService(
        repository=repo,
        matching_orchestrator=FakeMatchingOrchestrator(),
        cv_optimizer=None,
        interview_prep_service=None,
        profile_service=FakeProfileService(None),
    )
    with pytest.raises(ValueError, match="Profile"):
        await service.generate_match(uuid.uuid4(), cv_language="en")


@pytest.mark.asyncio
async def test_generate_optimization_pulls_missing_skills_from_match() -> None:
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="desc",
        required_skills=["python", "k8s"],
        source="manual",
    )
    repo = FakeRepo(snapshot=snap)
    # Pre-populate a match
    match = ApplicationMatch(
        id=uuid.uuid4(),
        application_id=app_id,
        overall_score=0.7,
        semantic_score=0.7,
        skill_score=0.5,
        experience_score=0.8,
        language_score=0.8,
        matched_skills=["python"],
        missing_skills=["k8s"],
        pros=[],
        cons=[],
        recommendations=["learn k8s"],
        cv_language="en",
    )
    repo.matches.append(match)

    profiles = FakeProfileService(
        FakeProfile("en", "summary", ["python"], raw_tex=r"\documentclass{}")
    )
    optimizer = FakeOptimizer()

    service = ArtifactService(
        repository=repo,
        matching_orchestrator=FakeMatchingOrchestrator(),
        cv_optimizer=optimizer,
        interview_prep_service=None,
        profile_service=profiles,
    )

    result = await service.generate_optimization(app_id, cv_language="en", match_id=None)
    assert result.optimized_tex == "OPT_TEX"
    assert optimizer.last_args["job_skills"] == ["python", "k8s"]
    assert optimizer.last_args["missing_skills"] == ["k8s"]


@pytest.mark.asyncio
async def test_generate_optimization_raises_without_match() -> None:
    snap = ApplicationJobSnapshot(
        application_id=uuid.uuid4(),
        description="d",
        required_skills=["x"],
        source="manual",
    )
    repo = FakeRepo(snapshot=snap)
    profiles = FakeProfileService(FakeProfile("en", "s", ["x"], raw_tex=r"\documentclass{}"))
    service = ArtifactService(
        repository=repo,
        matching_orchestrator=FakeMatchingOrchestrator(),
        cv_optimizer=FakeOptimizer(),
        interview_prep_service=None,
        profile_service=profiles,
    )
    with pytest.raises(ValueError, match="match"):
        await service.generate_optimization(uuid.uuid4(), cv_language="en", match_id=None)


@pytest.mark.asyncio
async def test_generate_interview_prep_uses_snapshot() -> None:
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="desc",
        required_skills=["x"],
        source="manual",
    )
    repo = FakeRepo(snapshot=snap)
    prep_service = FakeInterviewPrepService()

    class FakeTracked:
        title = "Software Engineer"
        company = "Fieldguide"

    class FakeTrackingForPrep:
        def get(self, _):
            return FakeTracked()

    service = ArtifactService(
        repository=repo,
        matching_orchestrator=FakeMatchingOrchestrator(),
        cv_optimizer=None,
        interview_prep_service=prep_service,
        profile_service=FakeProfileService(FakeProfile("en", "s", [])),
        tracking_service=FakeTrackingForPrep(),
    )

    result = await service.generate_interview_prep(app_id)
    assert result.competencies_to_probe == ["leadership"]
    assert prep_service.last_job["title"] == "Software Engineer"
    assert prep_service.last_job["company"] == "Fieldguide"
    assert prep_service.last_job["description"] == "desc"

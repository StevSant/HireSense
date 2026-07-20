from __future__ import annotations

import uuid
from typing import Any

from hiresense.applications.domain.aggregate import (
    ApplicationAggregate,
    CoverLetterView,
    CvOptimizationView,
    InterviewPrepView,
    JobSnapshotView,
    MatchView,
)
from hiresense.applications.domain.models import ApplicationJobSnapshot, JobSnapshotSource
from hiresense.applications.domain.skill_extractor import SkillExtractor
from hiresense.applications.ports import ApplicationRepositoryPort
from hiresense.kernel.exceptions import NotFoundError
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class ApplicationService:
    def __init__(
        self,
        repository: ApplicationRepositoryPort,
        tracking_service: Any,
        ingestion_orchestrator: Any,
        skill_extractor: SkillExtractor,
    ) -> None:
        self._repo = repository
        self._tracking = tracking_service
        self._ingestion = ingestion_orchestrator
        self._extractor = skill_extractor

    def list_all_cover_letters(self) -> list[dict[str, Any]]:
        return self._repo.list_all_cover_letters_with_context()

    async def create_from_ingested(self, job_id: str) -> ApplicationAggregate:
        job = self._ingestion.get_job_by_id(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")
        tracked = self._tracking.track_from_ingestion(job_id)
        description = getattr(job, "description", "") or ""
        skills = list(getattr(job, "skills", []) or [])
        source = JobSnapshotSource.INGESTED.value
        # Some normalizers (LinkedIn, HN Hiring) can't extract skills.
        # Fall back to LLM extraction when description is non-empty.
        if not skills and description:
            extracted = await self._extractor.extract(description)
            if extracted:
                skills = extracted
                source = JobSnapshotSource.LLM_EXTRACTED.value
        snapshot = ApplicationJobSnapshot(
            application_id=tracked.id,
            description=description,
            required_skills=skills,
            source=source,
        )
        self._repo.create_snapshot(snapshot)
        return self._build_aggregate(tracked)

    async def create_from_manual(
        self,
        title: str,
        company: str,
        description: str,
        url: str | None,
        notes: str | None = None,
    ) -> ApplicationAggregate:
        tracked = self._tracking.track_job(title=title, company=company, url=url, notes=notes)
        skills = await self._extractor.extract(description)
        source = JobSnapshotSource.LLM_EXTRACTED.value if skills else JobSnapshotSource.MANUAL.value
        snapshot = ApplicationJobSnapshot(
            application_id=tracked.id,
            description=description,
            required_skills=skills,
            source=source,
        )
        self._repo.create_snapshot(snapshot)
        return self._build_aggregate(tracked)

    def get(self, application_id: uuid.UUID) -> ApplicationAggregate:
        tracked = self._tracking.get(application_id)
        return self._build_aggregate(tracked)

    def list(self, status: ApplicationStatus | None = None) -> list[ApplicationAggregate]:
        tracked_list = self._tracking.list(status=status)
        return [self._build_aggregate(t) for t in tracked_list]

    def remove(self, application_id: uuid.UUID) -> None:
        self._tracking.remove(application_id)

    def update_snapshot(
        self,
        application_id: uuid.UUID,
        description: str | None = None,
        required_skills: list[str] | None = None,
    ) -> ApplicationAggregate:
        snap = self._repo.get_snapshot(application_id)
        if snap is None:
            raise NotFoundError(f"Snapshot for {application_id} not found")
        if description is not None:
            snap.description = description
        if required_skills is not None:
            snap.required_skills = required_skills
        self._repo.save_snapshot(snap)
        tracked = self._tracking.get(application_id)
        return self._build_aggregate(tracked)

    async def regenerate_skills(self, application_id: uuid.UUID) -> ApplicationAggregate:
        snap = self._repo.get_snapshot(application_id)
        if snap is None:
            raise NotFoundError(f"Snapshot for {application_id} not found")
        snap.required_skills = await self._extractor.extract(snap.description)
        if snap.required_skills:
            snap.source = JobSnapshotSource.LLM_EXTRACTED.value
        self._repo.save_snapshot(snap)
        tracked = self._tracking.get(application_id)
        return self._build_aggregate(tracked)

    # ----- internal ----------------------------------------------------

    def _build_aggregate(self, tracked: TrackedApplication) -> ApplicationAggregate:
        snap_orm = self._repo.get_snapshot(tracked.id)
        snap_view = (
            JobSnapshotView(
                id=snap_orm.id,
                description=snap_orm.description,
                required_skills=list(snap_orm.required_skills or []),
                source=snap_orm.source,
                updated_at=snap_orm.updated_at,
            )
            if snap_orm is not None
            else None
        )

        latest_match = self._repo.get_latest_match(tracked.id)
        match_view = (
            MatchView(
                id=latest_match.id,
                overall_score=latest_match.overall_score,
                semantic_score=latest_match.semantic_score,
                skill_score=latest_match.skill_score,
                experience_score=latest_match.experience_score,
                language_score=latest_match.language_score,
                matched_skills=list(latest_match.matched_skills or []),
                missing_skills=list(latest_match.missing_skills or []),
                pros=list(latest_match.pros or []),
                cons=list(latest_match.cons or []),
                recommendations=list(latest_match.recommendations or []),
                cv_language=latest_match.cv_language,
                created_at=latest_match.created_at,
            )
            if latest_match is not None
            else None
        )

        latest_opt = self._repo.get_latest_optimization(tracked.id)
        opt_view = (
            CvOptimizationView(
                id=latest_opt.id,
                match_id=latest_opt.match_id,
                cv_language=latest_opt.cv_language,
                original_tex=latest_opt.original_tex,
                optimized_tex=latest_opt.optimized_tex,
                improvement_summary=latest_opt.improvement_summary,
                changes=list(latest_opt.changes or []),
                created_at=latest_opt.created_at,
            )
            if latest_opt is not None
            else None
        )

        latest_prep = self._repo.get_latest_interview_prep(tracked.id)
        prep_view = (
            InterviewPrepView(
                id=latest_prep.id,
                competencies_to_probe=list(latest_prep.competencies_to_probe or []),
                technical_topics=list(latest_prep.technical_topics or []),
                negotiation_points=list(latest_prep.negotiation_points or []),
                matched_stories=list(latest_prep.matched_stories or []),
                created_at=latest_prep.created_at,
            )
            if latest_prep is not None
            else None
        )

        latest_letter = self._repo.get_latest_cover_letter(tracked.id)
        letter_view = (
            CoverLetterView(
                id=latest_letter.id,
                match_id=latest_letter.match_id,
                body=latest_letter.body,
                tone=latest_letter.tone,
                created_at=latest_letter.created_at,
            )
            if latest_letter is not None
            else None
        )
        cover_letter_count = len(self._repo.list_cover_letters(tracked.id))

        return ApplicationAggregate(
            id=tracked.id,
            job_id=tracked.job_id,
            title=tracked.title,
            company=tracked.company,
            url=tracked.url,
            status=tracked.status,
            notes=tracked.notes,
            applied_at=tracked.applied_at,
            created_at=tracked.created_at,
            updated_at=tracked.updated_at,
            job_snapshot=snap_view,
            latest_match=match_view,
            latest_optimization=opt_view,
            latest_interview_prep=prep_view,
            latest_cover_letter=letter_view,
            match_count=len(self._repo.list_matches(tracked.id)),
            optimization_count=len(self._repo.list_optimizations(tracked.id)),
            interview_prep_count=len(self._repo.list_interview_preps(tracked.id)),
            cover_letter_count=cover_letter_count,
        )

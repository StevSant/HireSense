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

    def list_all_cover_letters(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[dict[str, Any]]:
        return self._repo.list_all_cover_letters_with_context(limit=limit, offset=offset)

    def count_all_cover_letters(self) -> int:
        return self._repo.count_all_cover_letters()

    async def create_from_ingested(self, job_id: str) -> ApplicationAggregate:
        job = self._ingestion.get_job_by_id(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
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

    def list(
        self,
        status: ApplicationStatus | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ApplicationAggregate]:
        tracked_list = self._tracking.list(status=status, limit=limit, offset=offset)
        return self._build_aggregates(tracked_list)

    def count(self, status: ApplicationStatus | None = None) -> int:
        return self._tracking.count(status=status)

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
            raise ValueError(f"Snapshot for {application_id} not found")
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
            raise ValueError(f"Snapshot for {application_id} not found")
        snap.required_skills = await self._extractor.extract(snap.description)
        if snap.required_skills:
            snap.source = JobSnapshotSource.LLM_EXTRACTED.value
        self._repo.save_snapshot(snap)
        tracked = self._tracking.get(application_id)
        return self._build_aggregate(tracked)

    # ----- internal ----------------------------------------------------

    def _build_aggregate(self, tracked: TrackedApplication) -> ApplicationAggregate:
        return self._build_aggregates([tracked])[0]

    def _build_aggregates(
        self, tracked_list: list[TrackedApplication]
    ) -> list[ApplicationAggregate]:
        """Assemble aggregates for many tracked applications with a fixed number
        of queries — one batch load per child type — instead of ~10 queries per
        application. Each ``*_for`` call groups its rows by application_id and
        orders them newest-first, so ``[0]`` is the latest and ``len(...)`` the
        count without a second round-trip."""
        if not tracked_list:
            return []
        ids = [t.id for t in tracked_list]
        snapshots = self._repo.get_snapshots_for(ids)
        matches = self._repo.list_matches_for(ids)
        optimizations = self._repo.list_optimizations_for(ids)
        preps = self._repo.list_interview_preps_for(ids)
        letters = self._repo.list_cover_letters_for(ids)
        return [
            self._assemble(
                tracked,
                snapshots.get(tracked.id),
                matches.get(tracked.id, []),
                optimizations.get(tracked.id, []),
                preps.get(tracked.id, []),
                letters.get(tracked.id, []),
            )
            for tracked in tracked_list
        ]

    @staticmethod
    def _assemble(
        tracked: TrackedApplication,
        snap: Any,
        matches: list[Any],
        optimizations: list[Any],
        preps: list[Any],
        letters: list[Any],
    ) -> ApplicationAggregate:
        snap_view = (
            JobSnapshotView(
                id=snap.id,
                description=snap.description,
                required_skills=list(snap.required_skills or []),
                source=snap.source,
                updated_at=snap.updated_at,
            )
            if snap is not None
            else None
        )

        latest_match = matches[0] if matches else None
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

        latest_opt = optimizations[0] if optimizations else None
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

        latest_prep = preps[0] if preps else None
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

        latest_letter = letters[0] if letters else None
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
            match_count=len(matches),
            optimization_count=len(optimizations),
            interview_prep_count=len(preps),
            cover_letter_count=len(letters),
        )

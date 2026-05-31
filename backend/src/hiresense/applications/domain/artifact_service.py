from __future__ import annotations

import uuid
from typing import Any

from hiresense.applications.domain.aggregate import (
    CvOptimizationView,
    InterviewPrepView,
    MatchView,
)
from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationMatch,
)
from hiresense.applications.ports import ApplicationRepositoryPort
from hiresense.matching.domain import SkillMatcher


class ArtifactService:
    def __init__(
        self,
        repository: ApplicationRepositoryPort,
        matching_orchestrator: Any,
        cv_optimizer: Any,
        interview_prep_service: Any,
        profile_service: Any,
        tracking_service: Any | None = None,
    ) -> None:
        self._repo = repository
        self._matching = matching_orchestrator
        self._optimizer = cv_optimizer
        self._prep = interview_prep_service
        self._profiles = profile_service
        self._tracking = tracking_service

    async def generate_match(
        self,
        application_id: uuid.UUID,
        cv_language: str,
    ) -> MatchView:
        snapshot = self._repo.get_snapshot(application_id)
        if snapshot is None:
            raise ValueError(f"Snapshot for {application_id} not found")

        profile = self._profiles.get_for_language(cv_language)
        if profile is None:
            raise ValueError(f"Profile for language '{cv_language}' not found")

        cv_summary = getattr(profile, "summary", "") or ""
        cv_skills = list(getattr(profile, "skills", []) or [])
        cv_text = getattr(profile, "raw_tex", "") or ""

        result = await self._matching.analyze(
            job_id=str(application_id),
            cv_id=cv_language,
            job_description=snapshot.description,
            job_skills=list(snapshot.required_skills or []),
            cv_summary=cv_summary,
            cv_skills=cv_skills,
            cv_text=cv_text,
        )

        # Fallback when the orchestrator returns no skill verdict: use the same
        # normalization + evidence logic so the result stays consistent with
        # what analyze() produces (no divergent exact-string set math).
        fallback = SkillMatcher().match(
            cv_skills,
            list(snapshot.required_skills or []),
            evidence_text="\n".join(filter(None, [cv_summary, cv_text])),
        )
        matched = fallback.matched
        missing = fallback.missing

        row = ApplicationMatch(
            application_id=application_id,
            overall_score=result.overall_score,
            semantic_score=result.breakdown.semantic_score,
            skill_score=result.breakdown.skill_score,
            experience_score=result.breakdown.experience_score,
            language_score=result.breakdown.language_score,
            matched_skills=list(result.matched_skills) if result.matched_skills else matched,
            missing_skills=list(result.missing_skills) if result.missing_skills else missing,
            pros=list(result.pros or []),
            cons=list(result.cons or []),
            recommendations=list(result.recommendations or []),
            cv_language=cv_language,
        )
        saved = self._repo.create_match(row)
        return MatchView(
            id=saved.id,
            overall_score=saved.overall_score,
            semantic_score=saved.semantic_score,
            skill_score=saved.skill_score,
            experience_score=saved.experience_score,
            language_score=saved.language_score,
            matched_skills=list(saved.matched_skills or []),
            missing_skills=list(saved.missing_skills or []),
            pros=list(saved.pros or []),
            cons=list(saved.cons or []),
            recommendations=list(saved.recommendations or []),
            cv_language=saved.cv_language,
            created_at=saved.created_at,
        )

    async def generate_optimization(
        self,
        application_id: uuid.UUID,
        cv_language: str,
        match_id: uuid.UUID | None,
    ) -> CvOptimizationView:
        snapshot = self._repo.get_snapshot(application_id)
        if snapshot is None:
            raise ValueError(f"Snapshot for {application_id} not found")

        if match_id is None:
            match = self._repo.get_latest_match(application_id)
        else:
            match = self._repo.get_match(match_id)
        if match is None:
            raise ValueError("No match found - run a match before optimizing")

        profile = self._profiles.get_for_language(cv_language)
        if profile is None:
            raise ValueError(f"Profile for language '{cv_language}' not found")

        original_tex = getattr(profile, "raw_tex", "") or ""

        result = await self._optimizer.optimize(
            match_id=str(match.id),
            job_id=str(application_id),
            cv_id=cv_language,
            original_tex=original_tex,
            job_description=snapshot.description,
            job_skills=list(snapshot.required_skills or []),
            missing_skills=list(match.missing_skills or []),
            recommendations=list(match.recommendations or []),
        )

        row = ApplicationCvOptimization(
            application_id=application_id,
            match_id=match.id,
            cv_language=cv_language,
            original_tex=original_tex,
            optimized_tex=result.optimized_tex,
            improvement_summary=getattr(result, "improvement_summary", "") or "",
            changes=[
                c.model_dump() if hasattr(c, "model_dump") else dict(c)
                for c in getattr(result, "changes", []) or []
            ],
        )
        saved = self._repo.create_optimization(row)
        return CvOptimizationView(
            id=saved.id,
            match_id=saved.match_id,
            cv_language=saved.cv_language,
            original_tex=saved.original_tex,
            optimized_tex=saved.optimized_tex,
            improvement_summary=saved.improvement_summary,
            changes=list(saved.changes or []),
            created_at=saved.created_at,
        )

    async def generate_interview_prep(
        self,
        application_id: uuid.UUID,
    ) -> InterviewPrepView:
        snapshot = self._repo.get_snapshot(application_id)
        if snapshot is None:
            raise ValueError(f"Snapshot for {application_id} not found")
        if self._tracking is None:
            raise RuntimeError("tracking_service not wired into ArtifactService")
        tracked = self._tracking.get(application_id)

        prep = await self._prep.prepare({
            "title": tracked.title,
            "company": tracked.company,
            "description": snapshot.description,
        })

        row = ApplicationInterviewPrep(
            application_id=application_id,
            competencies_to_probe=list(prep.competencies_to_probe or []),
            technical_topics=list(prep.technical_topics or []),
            negotiation_points=list(prep.negotiation_points or []),
            matched_stories=[
                {
                    "story_id": str(m.story_id),
                    "story_title": m.story_title,
                    "relevance": m.relevance,
                }
                for m in prep.matched_stories or []
            ],
        )
        saved = self._repo.create_interview_prep(row)
        return InterviewPrepView(
            id=saved.id,
            competencies_to_probe=list(saved.competencies_to_probe or []),
            technical_topics=list(saved.technical_topics or []),
            negotiation_points=list(saved.negotiation_points or []),
            matched_stories=list(saved.matched_stories or []),
            created_at=saved.created_at,
        )

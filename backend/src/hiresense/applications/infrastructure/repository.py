from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.applications.domain.models import (
    ApplicationCoverLetter,
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
)
from hiresense.applications.infrastructure.orm import (
    ApplicationCoverLetterOrm,
    ApplicationCvOptimizationOrm,
    ApplicationInterviewPrepOrm,
    ApplicationJobSnapshotOrm,
    ApplicationMatchOrm,
)
from hiresense.infrastructure import SqlRepository
from hiresense.tracking.infrastructure.orm import TrackedApplicationOrm

_SNAPSHOT_FIELDS = ("application_id", "description", "required_skills", "source")
_MATCH_FIELDS = (
    "application_id",
    "overall_score",
    "semantic_score",
    "skill_score",
    "experience_score",
    "language_score",
    "matched_skills",
    "missing_skills",
    "pros",
    "cons",
    "recommendations",
    "cv_language",
)
_OPT_FIELDS = (
    "application_id",
    "match_id",
    "cv_language",
    "original_tex",
    "optimized_tex",
    "improvement_summary",
    "changes",
)
_LETTER_FIELDS = ("application_id", "match_id", "body", "tone")
_PREP_FIELDS = (
    "application_id",
    "competencies_to_probe",
    "technical_topics",
    "negotiation_points",
    "matched_stories",
)


def _orm_kwargs(model: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(model, field) for field in fields}


class ApplicationRepository(SqlRepository):
    # ---- snapshots ----------------------------------------------------

    def create_snapshot(self, snapshot: ApplicationJobSnapshot) -> ApplicationJobSnapshot:
        row = ApplicationJobSnapshotOrm(**_orm_kwargs(snapshot, _SNAPSHOT_FIELDS))
        return self._insert(row, ApplicationJobSnapshot.model_validate)

    def get_snapshot(self, application_id: uuid.UUID) -> ApplicationJobSnapshot | None:
        stmt = select(ApplicationJobSnapshotOrm).where(
            ApplicationJobSnapshotOrm.application_id == application_id
        )
        return self._select_one(stmt, ApplicationJobSnapshot.model_validate)

    def save_snapshot(self, snapshot: ApplicationJobSnapshot) -> ApplicationJobSnapshot:
        with self._session_factory() as session:
            row = session.get(ApplicationJobSnapshotOrm, snapshot.id) if snapshot.id else None
            if row is None:
                row = ApplicationJobSnapshotOrm(**_orm_kwargs(snapshot, _SNAPSHOT_FIELDS))
                session.add(row)
            else:
                for field in _SNAPSHOT_FIELDS:
                    setattr(row, field, getattr(snapshot, field))
            session.commit()
            session.refresh(row)
            return ApplicationJobSnapshot.model_validate(row)

    # ---- matches ------------------------------------------------------

    def create_match(self, match: ApplicationMatch) -> ApplicationMatch:
        row = ApplicationMatchOrm(**_orm_kwargs(match, _MATCH_FIELDS))
        return self._insert(row, ApplicationMatch.model_validate)

    def list_matches(self, application_id: uuid.UUID) -> list[ApplicationMatch]:
        stmt = (
            select(ApplicationMatchOrm)
            .where(ApplicationMatchOrm.application_id == application_id)
            .order_by(ApplicationMatchOrm.created_at.desc())
        )
        return self._select_all(stmt, ApplicationMatch.model_validate)

    def get_latest_match(self, application_id: uuid.UUID) -> ApplicationMatch | None:
        matches = self.list_matches(application_id)
        return matches[0] if matches else None

    def get_match(self, match_id: uuid.UUID) -> ApplicationMatch | None:
        return self._get_by_pk(ApplicationMatchOrm, match_id, ApplicationMatch.model_validate)

    # ---- optimizations -----------------------------------------------

    def create_optimization(self, opt: ApplicationCvOptimization) -> ApplicationCvOptimization:
        row = ApplicationCvOptimizationOrm(**_orm_kwargs(opt, _OPT_FIELDS))
        return self._insert(row, ApplicationCvOptimization.model_validate)

    def list_optimizations(self, application_id: uuid.UUID) -> list[ApplicationCvOptimization]:
        stmt = (
            select(ApplicationCvOptimizationOrm)
            .where(ApplicationCvOptimizationOrm.application_id == application_id)
            .order_by(ApplicationCvOptimizationOrm.created_at.desc())
        )
        return self._select_all(stmt, ApplicationCvOptimization.model_validate)

    def get_latest_optimization(
        self, application_id: uuid.UUID
    ) -> ApplicationCvOptimization | None:
        opts = self.list_optimizations(application_id)
        return opts[0] if opts else None

    def get_optimization(self, optimization_id: uuid.UUID) -> ApplicationCvOptimization | None:
        return self._get_by_pk(
            ApplicationCvOptimizationOrm,
            optimization_id,
            ApplicationCvOptimization.model_validate,
        )

    # ---- interview preps ---------------------------------------------

    def create_interview_prep(self, prep: ApplicationInterviewPrep) -> ApplicationInterviewPrep:
        row = ApplicationInterviewPrepOrm(**_orm_kwargs(prep, _PREP_FIELDS))
        return self._insert(row, ApplicationInterviewPrep.model_validate)

    def list_interview_preps(self, application_id: uuid.UUID) -> list[ApplicationInterviewPrep]:
        stmt = (
            select(ApplicationInterviewPrepOrm)
            .where(ApplicationInterviewPrepOrm.application_id == application_id)
            .order_by(ApplicationInterviewPrepOrm.created_at.desc())
        )
        return self._select_all(stmt, ApplicationInterviewPrep.model_validate)

    def get_latest_interview_prep(
        self, application_id: uuid.UUID
    ) -> ApplicationInterviewPrep | None:
        preps = self.list_interview_preps(application_id)
        return preps[0] if preps else None

    # ---- cover letters -----------------------------------------------

    def create_cover_letter(self, letter: ApplicationCoverLetter) -> ApplicationCoverLetter:
        row = ApplicationCoverLetterOrm(**_orm_kwargs(letter, _LETTER_FIELDS))
        return self._insert(row, ApplicationCoverLetter.model_validate)

    def list_cover_letters(self, application_id: uuid.UUID) -> list[ApplicationCoverLetter]:
        stmt = (
            select(ApplicationCoverLetterOrm)
            .where(ApplicationCoverLetterOrm.application_id == application_id)
            .order_by(ApplicationCoverLetterOrm.created_at.desc())
        )
        return self._select_all(stmt, ApplicationCoverLetter.model_validate)

    def get_latest_cover_letter(self, application_id: uuid.UUID) -> ApplicationCoverLetter | None:
        letters = self.list_cover_letters(application_id)
        return letters[0] if letters else None

    def get_cover_letter(self, cover_letter_id: uuid.UUID) -> ApplicationCoverLetter | None:
        return self._get_by_pk(
            ApplicationCoverLetterOrm,
            cover_letter_id,
            ApplicationCoverLetter.model_validate,
        )

    def list_all_cover_letters_with_context(self) -> list[dict[str, Any]]:
        """Cross-application listing for the Cover Letter Library view."""
        with self._session_factory() as session:
            stmt = (
                select(
                    ApplicationCoverLetterOrm.id,
                    ApplicationCoverLetterOrm.application_id,
                    ApplicationCoverLetterOrm.body,
                    ApplicationCoverLetterOrm.tone,
                    ApplicationCoverLetterOrm.created_at,
                    TrackedApplicationOrm.title,
                    TrackedApplicationOrm.company,
                    TrackedApplicationOrm.url,
                )
                .join(
                    TrackedApplicationOrm,
                    TrackedApplicationOrm.id == ApplicationCoverLetterOrm.application_id,
                )
                .order_by(ApplicationCoverLetterOrm.created_at.desc())
            )
            rows = session.execute(stmt).all()
            return [
                {
                    "id": row.id,
                    "application_id": row.application_id,
                    "body": row.body,
                    "tone": row.tone,
                    "created_at": row.created_at,
                    "title": row.title,
                    "company": row.company,
                    "application_url": row.url,
                }
                for row in rows
            ]

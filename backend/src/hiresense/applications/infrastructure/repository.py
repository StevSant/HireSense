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


class ApplicationRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    # ---- snapshots ----------------------------------------------------

    def create_snapshot(self, snapshot: ApplicationJobSnapshot) -> ApplicationJobSnapshot:
        with self._session_factory() as session:
            row = ApplicationJobSnapshotOrm(**_orm_kwargs(snapshot, _SNAPSHOT_FIELDS))
            session.add(row)
            session.commit()
            session.refresh(row)
            return ApplicationJobSnapshot.model_validate(row)

    def get_snapshot(self, application_id: uuid.UUID) -> ApplicationJobSnapshot | None:
        with self._session_factory() as session:
            stmt = select(ApplicationJobSnapshotOrm).where(
                ApplicationJobSnapshotOrm.application_id == application_id
            )
            row = session.scalars(stmt).first()
            return ApplicationJobSnapshot.model_validate(row) if row else None

    def save_snapshot(self, snapshot: ApplicationJobSnapshot) -> ApplicationJobSnapshot:
        with self._session_factory() as session:
            row = (
                session.get(ApplicationJobSnapshotOrm, snapshot.id)
                if snapshot.id
                else None
            )
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
        with self._session_factory() as session:
            row = ApplicationMatchOrm(**_orm_kwargs(match, _MATCH_FIELDS))
            session.add(row)
            session.commit()
            session.refresh(row)
            return ApplicationMatch.model_validate(row)

    def list_matches(self, application_id: uuid.UUID) -> list[ApplicationMatch]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationMatchOrm)
                .where(ApplicationMatchOrm.application_id == application_id)
                .order_by(ApplicationMatchOrm.created_at.desc())
            )
            return [ApplicationMatch.model_validate(r) for r in session.scalars(stmt).all()]

    def get_latest_match(self, application_id: uuid.UUID) -> ApplicationMatch | None:
        matches = self.list_matches(application_id)
        return matches[0] if matches else None

    def get_match(self, match_id: uuid.UUID) -> ApplicationMatch | None:
        with self._session_factory() as session:
            row = session.get(ApplicationMatchOrm, match_id)
            return ApplicationMatch.model_validate(row) if row else None

    # ---- optimizations -----------------------------------------------

    def create_optimization(
        self, opt: ApplicationCvOptimization
    ) -> ApplicationCvOptimization:
        with self._session_factory() as session:
            row = ApplicationCvOptimizationOrm(**_orm_kwargs(opt, _OPT_FIELDS))
            session.add(row)
            session.commit()
            session.refresh(row)
            return ApplicationCvOptimization.model_validate(row)

    def list_optimizations(
        self, application_id: uuid.UUID
    ) -> list[ApplicationCvOptimization]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationCvOptimizationOrm)
                .where(ApplicationCvOptimizationOrm.application_id == application_id)
                .order_by(ApplicationCvOptimizationOrm.created_at.desc())
            )
            return [
                ApplicationCvOptimization.model_validate(r)
                for r in session.scalars(stmt).all()
            ]

    def get_latest_optimization(
        self, application_id: uuid.UUID
    ) -> ApplicationCvOptimization | None:
        opts = self.list_optimizations(application_id)
        return opts[0] if opts else None

    def get_optimization(
        self, optimization_id: uuid.UUID
    ) -> ApplicationCvOptimization | None:
        with self._session_factory() as session:
            row = session.get(ApplicationCvOptimizationOrm, optimization_id)
            return ApplicationCvOptimization.model_validate(row) if row else None

    # ---- interview preps ---------------------------------------------

    def create_interview_prep(
        self, prep: ApplicationInterviewPrep
    ) -> ApplicationInterviewPrep:
        with self._session_factory() as session:
            row = ApplicationInterviewPrepOrm(**_orm_kwargs(prep, _PREP_FIELDS))
            session.add(row)
            session.commit()
            session.refresh(row)
            return ApplicationInterviewPrep.model_validate(row)

    def list_interview_preps(
        self, application_id: uuid.UUID
    ) -> list[ApplicationInterviewPrep]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationInterviewPrepOrm)
                .where(ApplicationInterviewPrepOrm.application_id == application_id)
                .order_by(ApplicationInterviewPrepOrm.created_at.desc())
            )
            return [
                ApplicationInterviewPrep.model_validate(r)
                for r in session.scalars(stmt).all()
            ]

    def get_latest_interview_prep(
        self, application_id: uuid.UUID
    ) -> ApplicationInterviewPrep | None:
        preps = self.list_interview_preps(application_id)
        return preps[0] if preps else None

    # ---- cover letters -----------------------------------------------

    def create_cover_letter(
        self, letter: ApplicationCoverLetter
    ) -> ApplicationCoverLetter:
        with self._session_factory() as session:
            row = ApplicationCoverLetterOrm(**_orm_kwargs(letter, _LETTER_FIELDS))
            session.add(row)
            session.commit()
            session.refresh(row)
            return ApplicationCoverLetter.model_validate(row)

    def list_cover_letters(
        self, application_id: uuid.UUID
    ) -> list[ApplicationCoverLetter]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationCoverLetterOrm)
                .where(ApplicationCoverLetterOrm.application_id == application_id)
                .order_by(ApplicationCoverLetterOrm.created_at.desc())
            )
            return [
                ApplicationCoverLetter.model_validate(r)
                for r in session.scalars(stmt).all()
            ]

    def get_latest_cover_letter(
        self, application_id: uuid.UUID
    ) -> ApplicationCoverLetter | None:
        letters = self.list_cover_letters(application_id)
        return letters[0] if letters else None

    def get_cover_letter(
        self, cover_letter_id: uuid.UUID
    ) -> ApplicationCoverLetter | None:
        with self._session_factory() as session:
            row = session.get(ApplicationCoverLetterOrm, cover_letter_id)
            return ApplicationCoverLetter.model_validate(row) if row else None

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

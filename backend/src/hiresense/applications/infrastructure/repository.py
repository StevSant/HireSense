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
from hiresense.tracking.domain.models import TrackedApplication


class ApplicationRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    # ---- snapshots ----------------------------------------------------

    def create_snapshot(self, snapshot: ApplicationJobSnapshot) -> ApplicationJobSnapshot:
        with self._session_factory() as session:
            session.add(snapshot)
            session.commit()
            session.refresh(snapshot)
            return snapshot

    def get_snapshot(self, application_id: uuid.UUID) -> ApplicationJobSnapshot | None:
        with self._session_factory() as session:
            stmt = select(ApplicationJobSnapshot).where(
                ApplicationJobSnapshot.application_id == application_id
            )
            return session.scalars(stmt).first()

    def save_snapshot(self, snapshot: ApplicationJobSnapshot) -> ApplicationJobSnapshot:
        with self._session_factory() as session:
            merged = session.merge(snapshot)
            session.commit()
            session.refresh(merged)
            return merged

    # ---- matches ------------------------------------------------------

    def create_match(self, match: ApplicationMatch) -> ApplicationMatch:
        with self._session_factory() as session:
            session.add(match)
            session.commit()
            session.refresh(match)
            return match

    def list_matches(self, application_id: uuid.UUID) -> list[ApplicationMatch]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationMatch)
                .where(ApplicationMatch.application_id == application_id)
                .order_by(ApplicationMatch.created_at.desc())
            )
            return list(session.scalars(stmt).all())

    def get_latest_match(self, application_id: uuid.UUID) -> ApplicationMatch | None:
        matches = self.list_matches(application_id)
        return matches[0] if matches else None

    def get_match(self, match_id: uuid.UUID) -> ApplicationMatch | None:
        with self._session_factory() as session:
            return session.get(ApplicationMatch, match_id)

    # ---- optimizations -----------------------------------------------

    def create_optimization(
        self, opt: ApplicationCvOptimization
    ) -> ApplicationCvOptimization:
        with self._session_factory() as session:
            session.add(opt)
            session.commit()
            session.refresh(opt)
            return opt

    def list_optimizations(
        self, application_id: uuid.UUID
    ) -> list[ApplicationCvOptimization]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationCvOptimization)
                .where(ApplicationCvOptimization.application_id == application_id)
                .order_by(ApplicationCvOptimization.created_at.desc())
            )
            return list(session.scalars(stmt).all())

    def get_latest_optimization(
        self, application_id: uuid.UUID
    ) -> ApplicationCvOptimization | None:
        opts = self.list_optimizations(application_id)
        return opts[0] if opts else None

    # ---- interview preps ---------------------------------------------

    def create_interview_prep(
        self, prep: ApplicationInterviewPrep
    ) -> ApplicationInterviewPrep:
        with self._session_factory() as session:
            session.add(prep)
            session.commit()
            session.refresh(prep)
            return prep

    def list_interview_preps(
        self, application_id: uuid.UUID
    ) -> list[ApplicationInterviewPrep]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationInterviewPrep)
                .where(ApplicationInterviewPrep.application_id == application_id)
                .order_by(ApplicationInterviewPrep.created_at.desc())
            )
            return list(session.scalars(stmt).all())

    def get_latest_interview_prep(
        self, application_id: uuid.UUID
    ) -> ApplicationInterviewPrep | None:
        preps = self.list_interview_preps(application_id)
        return preps[0] if preps else None

    def get_optimization(
        self, optimization_id: uuid.UUID
    ) -> ApplicationCvOptimization | None:
        with self._session_factory() as session:
            return session.get(ApplicationCvOptimization, optimization_id)

    # ---- cover letters -----------------------------------------------

    def create_cover_letter(
        self, letter: ApplicationCoverLetter
    ) -> ApplicationCoverLetter:
        with self._session_factory() as session:
            session.add(letter)
            session.commit()
            session.refresh(letter)
            return letter

    def list_cover_letters(
        self, application_id: uuid.UUID
    ) -> list[ApplicationCoverLetter]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationCoverLetter)
                .where(ApplicationCoverLetter.application_id == application_id)
                .order_by(ApplicationCoverLetter.created_at.desc())
            )
            return list(session.scalars(stmt).all())

    def get_latest_cover_letter(
        self, application_id: uuid.UUID
    ) -> ApplicationCoverLetter | None:
        letters = self.list_cover_letters(application_id)
        return letters[0] if letters else None

    def get_cover_letter(
        self, cover_letter_id: uuid.UUID
    ) -> ApplicationCoverLetter | None:
        with self._session_factory() as session:
            return session.get(ApplicationCoverLetter, cover_letter_id)

    def list_all_cover_letters_with_apps(
        self,
    ) -> list[tuple[ApplicationCoverLetter, TrackedApplication]]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationCoverLetter, TrackedApplication)
                .join(
                    TrackedApplication,
                    ApplicationCoverLetter.application_id == TrackedApplication.id,
                )
                .order_by(ApplicationCoverLetter.created_at.desc())
            )
            return [(letter, app) for letter, app in session.execute(stmt).all()]

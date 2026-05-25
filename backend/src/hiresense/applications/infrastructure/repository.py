from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
)


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

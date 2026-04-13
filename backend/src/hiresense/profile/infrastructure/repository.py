from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.profile.domain.models import Profile


class ProfileRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get_by_id(self, id: uuid.UUID) -> Profile | None:
        with self._session_factory() as session:
            return session.get(Profile, id)

    def get_latest(self, language: str | None = None) -> Profile | None:
        with self._session_factory() as session:
            stmt = select(Profile).order_by(Profile.created_at.desc())
            if language:
                stmt = stmt.where(Profile.language == language)
            stmt = stmt.limit(1)
            return session.scalars(stmt).first()

    def list_all(self) -> list[Profile]:
        with self._session_factory() as session:
            stmt = select(Profile).order_by(Profile.created_at.desc())
            return list(session.scalars(stmt).all())

    def create(self, profile: Profile) -> Profile:
        with self._session_factory() as session:
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile

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

    def update_manual_fields(
        self, profile_id: uuid.UUID, fields: dict[str, str | None]
    ) -> Profile | None:
        allowed = {
            "name_override",
            "location_override",
            "linkedin_url",
            "github_url",
            "portfolio_url",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown profile field(s): {sorted(unknown)}")
        with self._session_factory() as session:
            profile = session.get(Profile, profile_id)
            if profile is None:
                return None
            for key, value in fields.items():
                setattr(profile, key, value)
            session.commit()
            session.refresh(profile)
            return profile

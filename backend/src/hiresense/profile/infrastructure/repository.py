from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.profile.domain.models import CandidateProfile, CVSection
from hiresense.profile.infrastructure.orm import ProfileOrm

_SHARED_LINK_FIELDS = ("linkedin_url", "github_url", "portfolio_url")


def _to_domain(row: ProfileOrm) -> CandidateProfile:
    sections = [
        CVSection(name=s.get("name", ""), content=s.get("content", ""))
        for s in (row.sections or [])
    ]
    return CandidateProfile(
        id=str(row.id),
        name=row.name,
        email=row.email,
        phone=row.phone,
        location=row.location,
        sections=sections,
        raw_tex=row.raw_tex or "",
        language=row.language,
        skills=row.skills or [],
        linkedin_url=row.linkedin_url,
        github_url=row.github_url,
        portfolio_url=row.portfolio_url,
    )


def _to_orm(profile: CandidateProfile, original_filename: str | None = None) -> ProfileOrm:
    return ProfileOrm(
        id=uuid.UUID(profile.id),
        name=profile.name,
        email=profile.email,
        phone=profile.phone,
        location=profile.location,
        sections=[{"name": s.name, "content": s.content} for s in profile.sections],
        raw_tex=profile.raw_tex,
        language=profile.language,
        skills=profile.skills,
        original_filename=original_filename,
        linkedin_url=profile.linkedin_url,
        github_url=profile.github_url,
        portfolio_url=profile.portfolio_url,
    )


class ProfileRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get_by_id(self, id: uuid.UUID) -> CandidateProfile | None:
        with self._session_factory() as session:
            row = session.get(ProfileOrm, id)
            return _to_domain(row) if row is not None else None

    def get_latest(self, language: str | None = None) -> CandidateProfile | None:
        with self._session_factory() as session:
            stmt = select(ProfileOrm).order_by(ProfileOrm.created_at.desc())
            if language:
                stmt = stmt.where(ProfileOrm.language == language)
            stmt = stmt.limit(1)
            row = session.scalars(stmt).first()
            return _to_domain(row) if row is not None else None

    def list_all(self) -> list[CandidateProfile]:
        with self._session_factory() as session:
            stmt = select(ProfileOrm).order_by(ProfileOrm.created_at.desc())
            return [_to_domain(r) for r in session.scalars(stmt).all()]

    def create(
        self, profile: CandidateProfile, *, original_filename: str | None = None
    ) -> CandidateProfile:
        with self._session_factory() as session:
            row = _to_orm(profile, original_filename=original_filename)
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def update(self, id: uuid.UUID, fields: dict[str, Any]) -> CandidateProfile | None:
        with self._session_factory() as session:
            row = session.get(ProfileOrm, id)
            if row is None:
                return None
            for key, value in fields.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def update_all(self, fields: dict[str, Any]) -> int:
        """Set the given fields on every profile row. Used for fields that
        are conceptually one-per-person (linkedin/github/portfolio) so a
        Spanish-vs-English language switch doesn't lose them."""
        if not fields:
            return 0
        with self._session_factory() as session:
            rows = list(session.scalars(select(ProfileOrm)).all())
            for row in rows:
                for key, value in fields.items():
                    if hasattr(row, key):
                        setattr(row, key, value)
            session.commit()
            return len(rows)

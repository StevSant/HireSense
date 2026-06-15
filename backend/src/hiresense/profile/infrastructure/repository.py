from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.infrastructure import SqlRepository
from hiresense.profile.domain.apply_profile import ApplyProfile
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
        apply_profile=(
            ApplyProfile.model_validate(row.apply_profile)
            if row.apply_profile
            else None
        ),
        machine_translated=row.machine_translated,
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
        apply_profile=(
            profile.apply_profile.model_dump() if profile.apply_profile else None
        ),
        machine_translated=profile.machine_translated,
    )


class ProfileRepository(SqlRepository):
    def get_by_id(self, id: uuid.UUID) -> CandidateProfile | None:
        return self._get_by_pk(ProfileOrm, id, _to_domain)

    def get_latest(self, language: str | None = None) -> CandidateProfile | None:
        stmt = select(ProfileOrm).order_by(ProfileOrm.created_at.desc())
        if language:
            stmt = stmt.where(ProfileOrm.language == language)
        stmt = stmt.limit(1)
        return self._select_one(stmt, _to_domain)

    def list_all(self) -> list[CandidateProfile]:
        stmt = select(ProfileOrm).order_by(ProfileOrm.created_at.desc())
        return self._select_all(stmt, _to_domain)

    def create(
        self, profile: CandidateProfile, *, original_filename: str | None = None
    ) -> CandidateProfile:
        row = _to_orm(profile, original_filename=original_filename)
        return self._insert(row, _to_domain)

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

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.profile.cover_letter_templates.orm import CoverLetterTemplate


class CoverLetterTemplateRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def list_all(self) -> list[CoverLetterTemplate]:
        with self._session_factory() as session:
            stmt = select(CoverLetterTemplate).order_by(CoverLetterTemplate.created_at.desc())
            return list(session.scalars(stmt).all())

    def get_by_id(self, template_id: uuid.UUID) -> CoverLetterTemplate | None:
        with self._session_factory() as session:
            return session.get(CoverLetterTemplate, template_id)

    def create(self, template: CoverLetterTemplate) -> CoverLetterTemplate:
        with self._session_factory() as session:
            session.add(template)
            session.commit()
            session.refresh(template)
            return template

    def update(
        self, template_id: uuid.UUID, fields: dict[str, str]
    ) -> CoverLetterTemplate | None:
        allowed = {"name", "body", "tone", "language"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown template field(s): {sorted(unknown)}")
        with self._session_factory() as session:
            template = session.get(CoverLetterTemplate, template_id)
            if template is None:
                return None
            for key, value in fields.items():
                setattr(template, key, value)
            session.commit()
            session.refresh(template)
            return template

    def delete(self, template_id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            template = session.get(CoverLetterTemplate, template_id)
            if template is None:
                return False
            session.delete(template)
            session.commit()
            return True

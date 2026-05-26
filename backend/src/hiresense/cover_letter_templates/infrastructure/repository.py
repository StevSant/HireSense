from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.cover_letter_templates.domain.orm import CoverLetterTemplateOrm


class CoverLetterTemplateRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def list_all(self) -> list[CoverLetterTemplateOrm]:
        with self._session_factory() as session:
            stmt = select(CoverLetterTemplateOrm).order_by(
                CoverLetterTemplateOrm.updated_at.desc()
            )
            return list(session.scalars(stmt).all())

    def get(self, id: uuid.UUID) -> CoverLetterTemplateOrm | None:
        with self._session_factory() as session:
            return session.get(CoverLetterTemplateOrm, id)

    def create(self, template: CoverLetterTemplateOrm) -> CoverLetterTemplateOrm:
        with self._session_factory() as session:
            session.add(template)
            session.commit()
            session.refresh(template)
            return template

    def update(
        self, id: uuid.UUID, fields: dict[str, Any]
    ) -> CoverLetterTemplateOrm | None:
        with self._session_factory() as session:
            row = session.get(CoverLetterTemplateOrm, id)
            if row is None:
                return None
            for key, value in fields.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return row

    def delete(self, id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            row = session.get(CoverLetterTemplateOrm, id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

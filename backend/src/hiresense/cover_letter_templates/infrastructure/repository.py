from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.cover_letter_templates.domain.models import CoverLetterTemplate
from hiresense.cover_letter_templates.infrastructure.orm import CoverLetterTemplateOrm


def _to_domain(row: CoverLetterTemplateOrm) -> CoverLetterTemplate:
    return CoverLetterTemplate(
        id=row.id,
        name=row.name,
        tone=row.tone,
        language=row.language,
        opening=row.opening,
        body=row.body,
        signature=row.signature,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class CoverLetterTemplateRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def list_all(self) -> list[CoverLetterTemplate]:
        with self._session_factory() as session:
            stmt = select(CoverLetterTemplateOrm).order_by(
                CoverLetterTemplateOrm.updated_at.desc()
            )
            return [_to_domain(r) for r in session.scalars(stmt).all()]

    def get(self, id: uuid.UUID) -> CoverLetterTemplate | None:
        with self._session_factory() as session:
            row = session.get(CoverLetterTemplateOrm, id)
            return _to_domain(row) if row is not None else None

    def create(
        self,
        *,
        name: str,
        tone: str,
        language: str,
        opening: str,
        body: str,
        signature: str,
    ) -> CoverLetterTemplate:
        with self._session_factory() as session:
            row = CoverLetterTemplateOrm(
                name=name,
                tone=tone,
                language=language,
                opening=opening,
                body=body,
                signature=signature,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def update(self, id: uuid.UUID, fields: dict[str, Any]) -> CoverLetterTemplate | None:
        with self._session_factory() as session:
            row = session.get(CoverLetterTemplateOrm, id)
            if row is None:
                return None
            for key, value in fields.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def delete(self, id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            row = session.get(CoverLetterTemplateOrm, id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

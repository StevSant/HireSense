from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.cover_letter_templates.domain.models import CoverLetterTemplate
from hiresense.cover_letter_templates.infrastructure.orm import CoverLetterTemplateOrm
from hiresense.infrastructure import SqlRepository


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


class CoverLetterTemplateRepository(SqlRepository):
    def list_all(self) -> list[CoverLetterTemplate]:
        stmt = select(CoverLetterTemplateOrm).order_by(CoverLetterTemplateOrm.updated_at.desc())
        return self._select_all(stmt, _to_domain)

    def get(self, id: uuid.UUID) -> CoverLetterTemplate | None:
        return self._get_by_pk(CoverLetterTemplateOrm, id, _to_domain)

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
        row = CoverLetterTemplateOrm(
            name=name,
            tone=tone,
            language=language,
            opening=opening,
            body=body,
            signature=signature,
        )
        return self._insert(row, _to_domain)

    def update(self, id: uuid.UUID, fields: dict[str, Any]) -> CoverLetterTemplate | None:
        known = {
            key: value for key, value in fields.items() if hasattr(CoverLetterTemplateOrm, key)
        }
        return self._update_by_pk(CoverLetterTemplateOrm, id, known, _to_domain)

    def delete(self, id: uuid.UUID) -> bool:
        return self._delete_by_pk(CoverLetterTemplateOrm, id)

from __future__ import annotations

import uuid

from hiresense.cover_letter_templates.domain.models import CoverLetterTemplate
from hiresense.cover_letter_templates.domain.orm import CoverLetterTemplateOrm
from hiresense.cover_letter_templates.ports import CoverLetterTemplateRepositoryPort


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


_EDITABLE_FIELDS = ("name", "tone", "language", "opening", "body", "signature")


class CoverLetterTemplateService:
    def __init__(self, repository: CoverLetterTemplateRepositoryPort) -> None:
        self._repo = repository

    def list(self) -> list[CoverLetterTemplate]:
        return [_to_domain(r) for r in self._repo.list_all()]

    def get(self, template_id: uuid.UUID) -> CoverLetterTemplate | None:
        row = self._repo.get(template_id)
        return _to_domain(row) if row is not None else None

    def create(
        self,
        *,
        name: str,
        tone: str = "professional",
        language: str = "en",
        opening: str = "",
        body: str = "",
        signature: str = "",
    ) -> CoverLetterTemplate:
        if not name.strip():
            raise ValueError("name is required")
        row = CoverLetterTemplateOrm(
            name=name.strip(),
            tone=tone or "professional",
            language=language or "en",
            opening=opening,
            body=body,
            signature=signature,
        )
        saved = self._repo.create(row)
        return _to_domain(saved)

    def update(
        self, template_id: uuid.UUID, updates: dict[str, str | None]
    ) -> CoverLetterTemplate | None:
        sanitised: dict[str, str] = {}
        for key in _EDITABLE_FIELDS:
            if key not in updates:
                continue
            value = updates[key]
            if value is None:
                continue
            if key == "name":
                stripped = value.strip()
                if not stripped:
                    raise ValueError("name cannot be blank")
                sanitised[key] = stripped
            else:
                sanitised[key] = value
        if not sanitised:
            return self.get(template_id)
        row = self._repo.update(template_id, sanitised)
        return _to_domain(row) if row is not None else None

    def delete(self, template_id: uuid.UUID) -> bool:
        return self._repo.delete(template_id)

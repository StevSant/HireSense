from __future__ import annotations

import uuid

from hiresense.profile.cover_letter_templates.orm import CoverLetterTemplate
from hiresense.profile.cover_letter_templates.repository import CoverLetterTemplateRepository
from hiresense.profile.cover_letter_templates.view import CoverLetterTemplateView


class CoverLetterTemplateService:
    def __init__(self, repository: CoverLetterTemplateRepository) -> None:
        self._repo = repository

    def list(self) -> list[CoverLetterTemplateView]:
        return [self._to_view(t) for t in self._repo.list_all()]

    def get(self, template_id: uuid.UUID) -> CoverLetterTemplateView | None:
        template = self._repo.get_by_id(template_id)
        return self._to_view(template) if template else None

    def get_body(self, template_id: uuid.UUID) -> str | None:
        """Used by the cover letter generator — returns just the body text or None."""
        template = self._repo.get_by_id(template_id)
        return template.body if template else None

    def create(
        self, name: str, body: str, tone: str = "professional", language: str = "en"
    ) -> CoverLetterTemplateView:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        if not body or not body.strip():
            raise ValueError("body must not be empty")
        template = CoverLetterTemplate(
            name=name.strip(),
            body=body,
            tone=tone,
            language=language,
        )
        created = self._repo.create(template)
        return self._to_view(created)

    def update(
        self, template_id: uuid.UUID, fields: dict[str, str]
    ) -> CoverLetterTemplateView | None:
        cleaned: dict[str, str] = {}
        for key, value in fields.items():
            if key in {"name", "body"} and (not value or not value.strip()):
                raise ValueError(f"{key} must not be empty")
            cleaned[key] = value.strip() if key == "name" and value else value
        updated = self._repo.update(template_id, cleaned)
        return self._to_view(updated) if updated else None

    def delete(self, template_id: uuid.UUID) -> bool:
        return self._repo.delete(template_id)

    def _to_view(self, t: CoverLetterTemplate) -> CoverLetterTemplateView:
        return CoverLetterTemplateView(
            id=t.id,
            name=t.name,
            body=t.body,
            tone=t.tone,
            language=t.language,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )

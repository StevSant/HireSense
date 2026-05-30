from __future__ import annotations

import uuid
from typing import Any, Protocol

from hiresense.cover_letter_templates.domain.models import CoverLetterTemplate


class CoverLetterTemplateRepositoryPort(Protocol):
    def list_all(self) -> list[CoverLetterTemplate]: ...

    def get(self, id: uuid.UUID) -> CoverLetterTemplate | None: ...

    def create(
        self,
        *,
        name: str,
        tone: str,
        language: str,
        opening: str,
        body: str,
        signature: str,
    ) -> CoverLetterTemplate: ...

    def update(self, id: uuid.UUID, fields: dict[str, Any]) -> CoverLetterTemplate | None: ...

    def delete(self, id: uuid.UUID) -> bool: ...

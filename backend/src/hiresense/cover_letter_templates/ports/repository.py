from __future__ import annotations

import uuid
from typing import Any, Protocol

from hiresense.cover_letter_templates.domain.orm import CoverLetterTemplateOrm


class CoverLetterTemplateRepositoryPort(Protocol):
    def list_all(self) -> list[CoverLetterTemplateOrm]: ...

    def get(self, id: uuid.UUID) -> CoverLetterTemplateOrm | None: ...

    def create(self, template: CoverLetterTemplateOrm) -> CoverLetterTemplateOrm: ...

    def update(self, id: uuid.UUID, fields: dict[str, Any]) -> CoverLetterTemplateOrm | None: ...

    def delete(self, id: uuid.UUID) -> bool: ...

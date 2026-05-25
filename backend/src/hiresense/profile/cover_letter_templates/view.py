from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CoverLetterTemplateView(BaseModel):
    id: uuid.UUID
    name: str
    body: str
    tone: str
    language: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

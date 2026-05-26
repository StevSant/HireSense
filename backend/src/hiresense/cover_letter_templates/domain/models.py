from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CoverLetterTemplate(BaseModel):
    id: uuid.UUID
    name: str
    tone: str
    language: str
    opening: str
    body: str
    signature: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

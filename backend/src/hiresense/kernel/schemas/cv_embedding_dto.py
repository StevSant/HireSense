from __future__ import annotations

from pydantic import BaseModel


class CVEmbeddingDTO(BaseModel):
    cv_id: str
    embedding: list[float]

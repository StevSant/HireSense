from __future__ import annotations

from pydantic import BaseModel


class DigestEntry(BaseModel):
    """One job in a digest — a denormalized snapshot, stable after the job closes."""

    job_id: str
    title: str
    company: str
    url: str | None = None
    score: float

    model_config = {"from_attributes": True}

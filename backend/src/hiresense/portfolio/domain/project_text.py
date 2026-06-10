from __future__ import annotations

from pydantic import BaseModel


class ProjectText(BaseModel):
    """One language's title/description for a portfolio project."""

    title: str
    description: str | None = None

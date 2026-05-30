from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel


class Competency(str, enum.Enum):
    LEADERSHIP = "leadership"
    PROBLEM_SOLVING = "problem_solving"
    COLLABORATION = "collaboration"
    COMMUNICATION = "communication"
    ADAPTABILITY = "adaptability"
    TECHNICAL = "technical"
    INITIATIVE = "initiative"
    CONFLICT_RESOLUTION = "conflict_resolution"


class Story(BaseModel):
    """Domain model for a STAR interview story."""

    id: uuid.UUID | None = None
    title: str
    competency: str
    situation: str
    task: str
    action: str
    result: str
    reflection: str | None = None
    tags: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

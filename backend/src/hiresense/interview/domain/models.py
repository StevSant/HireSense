from __future__ import annotations

import enum
import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class Competency(str, enum.Enum):
    LEADERSHIP = "leadership"
    PROBLEM_SOLVING = "problem_solving"
    COLLABORATION = "collaboration"
    COMMUNICATION = "communication"
    ADAPTABILITY = "adaptability"
    TECHNICAL = "technical"
    INITIATIVE = "initiative"
    CONFLICT_RESOLUTION = "conflict_resolution"


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    competency: Mapped[str] = mapped_column(String(30), nullable=False)
    situation: Mapped[str] = mapped_column(Text, nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    reflection: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

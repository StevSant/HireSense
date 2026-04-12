from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Index, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class CVSection(BaseModel):
    name: str
    content: str


class CandidateProfile(BaseModel):
    id: str
    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    sections: list[CVSection] = Field(default_factory=list)
    raw_tex: str = ""
    language: str = "en"
    skills: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        Index("ix_profiles_created_at", "created_at"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sections: Mapped[list | None] = mapped_column(JSON, nullable=True)
    raw_tex: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

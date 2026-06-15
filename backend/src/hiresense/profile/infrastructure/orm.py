from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from hiresense.infrastructure.database import Base


class ProfileOrm(Base):
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
    linkedin_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # One-per-person Apply Assist answer bank (ApplyProfile), stored as JSON.
    apply_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    machine_translated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=expression.false()
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

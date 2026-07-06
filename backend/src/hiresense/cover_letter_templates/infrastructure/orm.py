from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class CoverLetterTemplateOrm(Base):
    __tablename__ = "cover_letter_templates"
    __table_args__ = (Index("ix_cover_letter_templates_updated_at", "updated_at"),)

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tone: Mapped[str] = mapped_column(String(20), default="professional")
    language: Mapped[str] = mapped_column(String(10), default="en")
    opening: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    signature: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

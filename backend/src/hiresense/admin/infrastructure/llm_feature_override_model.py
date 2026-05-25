from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class LLMFeatureOverride(Base):
    """Per-feature override of the global LLM config.

    `provider` / `model` are nullable: NULL means "inherit from global". When
    both are NULL the row is effectively a no-op (kept so the UI can store
    feature-specific `extra_params` like a custom temperature).
    """

    __tablename__ = "llm_feature_overrides"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    feature_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extra_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

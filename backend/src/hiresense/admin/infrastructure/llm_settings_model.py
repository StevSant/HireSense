from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class LLMSettings(Base):
    """Single-row table holding the global runtime LLM configuration.

    The row is keyed `id=1` and is upserted via the admin API. `api_key_encrypted`
    holds the Fernet ciphertext of the API key — never the plaintext.
    """

    __tablename__ = "llm_settings"
    __table_args__ = (CheckConstraint("id = 1", name="llm_settings_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

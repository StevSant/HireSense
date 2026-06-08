from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base

# Embeddings are stored as JSON float arrays (not a pgvector column): the taste
# math runs in Python and the ANN query targets the separate vector_embeddings
# table, so no pgvector type is needed here. This keeps the tables portable to
# the sqlite-backed unit/integration harness, matching the project's choice to
# keep the `vector` type off ORM models.


class FeedbackSignalOrm(Base):
    __tablename__ = "feedback_signals"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    job_id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    job_embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Per-dimension matching scores snapshotted at outcome time. NULL for
    # explicit signals (or when capture failed); maps back to domain `None`.
    dimension_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PreferenceModelOrm(Base):
    __tablename__ = "preference_models"

    # Singleton: one row, fixed id. (Multi-profile is a future extension.)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    delta_vector: Mapped[list] = mapped_column(JSON)
    # Phase 2: dimension name -> integer weight delta for the matching composite.
    # Defaults to {} so pre-Phase-2 rows (NULL) read back as "no overrides".
    weight_overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

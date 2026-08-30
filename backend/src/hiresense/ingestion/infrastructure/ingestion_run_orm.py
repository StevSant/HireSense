from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.shared.infrastructure.database import Base


class IngestionRunOrm(Base):
    """One ingestion pass: when it started, when it ended, how it was triggered."""

    __tablename__ = "ingestion_runs"
    # Declared here to match migration 045, which creates it. Without this the
    # alembic drift check sees an index in the DB that the model does not know
    # about and proposes dropping it.
    __table_args__ = (Index("ix_ingestion_runs_started_at", "started_at"),)

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL while the pass is still in flight.
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

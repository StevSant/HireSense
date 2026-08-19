from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.shared.infrastructure.database import Base


class JobHistoryEventOrm(Base):
    """One observed lifecycle change to one job.

    `run_id` is nullable on purpose: closures produced by the URL-probe
    revalidation sweep do not belong to an ingestion run, and inventing a
    synthetic run to satisfy NOT NULL would misrepresent when they happened.
    """

    __tablename__ = "job_history_events"
    __table_args__ = (
        Index("ix_job_history_events_job_occurred", "job_id", "occurred_at"),
        Index("ix_job_history_events_run", "run_id"),
        Index("ix_job_history_events_occurred", "occurred_at"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    # String(36) matches ingested_jobs.id exactly; a type mismatch would make
    # the FK unbuildable on PostgreSQL.
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ingested_jobs.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid_mod.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True
    )
    event: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_fields: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.shared.infrastructure.database import Base


class SubmissionAttemptOrm(Base):
    """One attempt to submit one application to one employer form."""

    __tablename__ = "submission_attempts"
    __table_args__ = (
        Index("ix_submission_attempts_status_created", "status", "created_at"),
        Index("ix_submission_attempts_application", "application_id"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    application_id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, nullable=False)
    job_id: Mapped[str] = mapped_column(String(128), nullable=False)
    packet_id: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalated_fields: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    runner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

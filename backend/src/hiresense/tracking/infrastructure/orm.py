from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, Uuid, event, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base
from hiresense.tracking.domain.models import ApplicationStatus


class TrackedApplicationOrm(Base):
    __tablename__ = "tracked_applications"
    __table_args__ = (
        Index("ix_tracked_applications_status", "status"),
        Index("ix_tracked_applications_job_id", "job_id"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    job_id: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ApplicationStatus.SAVED.value)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


@event.listens_for(TrackedApplicationOrm, "init")
def _set_defaults(target: TrackedApplicationOrm, args: tuple, kwargs: dict) -> None:
    if "status" not in kwargs:
        target.status = ApplicationStatus.SAVED.value

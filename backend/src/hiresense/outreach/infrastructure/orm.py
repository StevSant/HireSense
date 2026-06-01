from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class OutreachEventOrm(Base):
    """Append-only log of outreach actions on a tracked application."""

    __tablename__ = "outreach_events"
    __table_args__ = (
        Index("ix_outreach_events_application_id", "application_id"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    application_id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),  # microsecond precision (SQLite-deterministic)
        server_default=func.now(),
        nullable=False,
    )

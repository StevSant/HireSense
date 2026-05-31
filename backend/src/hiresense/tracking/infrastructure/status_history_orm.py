from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class ApplicationStatusHistoryOrm(Base):
    """Append-only log of tracked-application status transitions.

    Written transactionally with the status change (never via the event bus),
    so the funnel analytics never miss a transition. `from_status` is NULL on
    the seed row created when an application is first tracked.
    """

    __tablename__ = "application_status_history"
    __table_args__ = (
        Index("ix_application_status_history_application_id", "application_id"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    application_id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

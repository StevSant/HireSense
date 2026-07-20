from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class AutopilotDraftOrm(Base):
    """One job processed by an autopilot pipeline run."""

    __tablename__ = "autopilot_drafts"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    # Unique so a reserved draft is the idempotency guard: two concurrent runs
    # racing on the same job can never both insert a row (see DraftRepositoryImpl.claim).
    job_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    application_id: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    company: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class DigestOrm(Base):
    """One auto-hunt run. `created_at` is the watermark for the next run;
    `entries` is a denormalized JSON snapshot of the qualifying matches."""

    __tablename__ = "digests"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entries: Mapped[list] = mapped_column(JSON, default=list)
    job_count: Mapped[int] = mapped_column(Integer, default=0)

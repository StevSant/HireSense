from __future__ import annotations

import uuid as uuid_mod
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.shared.infrastructure.database import Base


class OpportunityOrm(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        UniqueConstraint("source", "identity_key", name="ux_opportunities_source_identity"),
        Index("ix_opportunities_kind", "kind"),
        Index("ix_opportunities_status", "status"),
        Index("ix_opportunities_country", "country"),
        Index("ix_opportunities_cfp_deadline", "cfp_deadline"),
        Index("ix_opportunities_application_deadline", "application_deadline"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="event")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    organization: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    apply_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    topics: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cfp_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    application_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    funding: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

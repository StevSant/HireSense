from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class NetworkContactOrm(Base):
    """One imported LinkedIn connection (full-snapshot replacement model)."""

    __tablename__ = "network_contacts"
    __table_args__ = (
        Index("ix_network_contacts_company_normalized", "company_normalized"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(256), nullable=False)
    last_name: Mapped[str] = mapped_column(String(256), nullable=False)
    company: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    position: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    company_normalized: Mapped[str] = mapped_column(String(512), nullable=False)
    linkedin_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    email: Mapped[str | None] = mapped_column(String(512), nullable=True)
    connected_on: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

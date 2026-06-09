from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure import JSONB_OR_JSON
from hiresense.infrastructure.database import Base


class PortfolioProjectOrm(Base):
    """Snapshot row for one synced portfolio project (replaced per sync)."""

    __tablename__ = "portfolio_projects"
    __table_args__ = (
        UniqueConstraint("source", "source_key", name="ux_portfolio_projects_source_key"),
        Index("ix_portfolio_projects_source", "source"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    demo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tech: Mapped[list] = mapped_column(JSONB_OR_JSON, default=list)
    translations: Mapped[dict] = mapped_column(JSONB_OR_JSON, default=dict)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

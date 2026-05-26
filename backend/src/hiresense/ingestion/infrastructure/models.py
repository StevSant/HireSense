from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class IngestedJob(Base):
    __tablename__ = "ingested_jobs"
    __table_args__ = (
        UniqueConstraint("bucket", "dedup_key", name="ux_ingested_jobs_bucket_dedup"),
        Index("ix_ingested_jobs_bucket_fetched_at", "bucket", "fetched_at"),
        Index("ix_ingested_jobs_source", "source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bucket: Mapped[str] = mapped_column(String(20), nullable=False, default="boards")
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(Text, default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(Text, default="")
    salary_range: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    url: Mapped[str] = mapped_column(String(2048), default="")
    posted_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    department: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    countries: Mapped[list] = mapped_column(JSON, default=list)
    remote_modality: Mapped[str | None] = mapped_column(String(20), nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

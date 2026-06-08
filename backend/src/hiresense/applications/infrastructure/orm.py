from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class ApplicationJobSnapshotOrm(Base):
    __tablename__ = "application_job_snapshots"

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    application_id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid,
        ForeignKey("tracked_applications.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ApplicationMatchOrm(Base):
    __tablename__ = "application_matches"
    __table_args__ = (
        Index("ix_application_matches_app_created", "application_id", "created_at"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    application_id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, ForeignKey("tracked_applications.id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_score: Mapped[float] = mapped_column(Float, nullable=False)
    skill_score: Mapped[float] = mapped_column(Float, nullable=False)
    experience_score: Mapped[float] = mapped_column(Float, nullable=False)
    language_score: Mapped[float] = mapped_column(Float, nullable=False)
    matched_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    pros: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recommendations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cv_language: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApplicationCvOptimizationOrm(Base):
    __tablename__ = "application_cv_optimizations"
    __table_args__ = (
        Index("ix_application_cv_opts_app_created", "application_id", "created_at"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    application_id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, ForeignKey("tracked_applications.id", ondelete="CASCADE"), nullable=False
    )
    match_id: Mapped[uuid_mod.UUID | None] = mapped_column(
        Uuid, ForeignKey("application_matches.id", ondelete="SET NULL"), nullable=True
    )
    cv_language: Mapped[str] = mapped_column(String(10), nullable=False)
    original_tex: Mapped[str] = mapped_column(Text, nullable=False)
    optimized_tex: Mapped[str] = mapped_column(Text, nullable=False)
    improvement_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    changes: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApplicationCoverLetterOrm(Base):
    __tablename__ = "application_cover_letters"
    __table_args__ = (
        Index("ix_application_cover_letters_app_created", "application_id", "created_at"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    application_id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, ForeignKey("tracked_applications.id", ondelete="CASCADE"), nullable=False
    )
    match_id: Mapped[uuid_mod.UUID | None] = mapped_column(
        Uuid, ForeignKey("application_matches.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(20), nullable=False, default="professional")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApplicationInterviewPrepOrm(Base):
    __tablename__ = "application_interview_preps"
    __table_args__ = (
        Index("ix_application_interview_preps_app_created", "application_id", "created_at"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    application_id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, ForeignKey("tracked_applications.id", ondelete="CASCADE"), nullable=False
    )
    competencies_to_probe: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    technical_topics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    negotiation_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_stories: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class JobMatchCache(Base):
    """Per-profile cache of LLM match scoring for a job.

    Keyed by (job_id, profile_hash) so scores are correct per candidate profile
    and self-invalidate when the CV changes (a new profile_hash misses the
    cache and triggers recompute). Holds both the Tier-1 quick score (shown on
    the list) and the Tier-2 deep analysis (loaded on demand); either side may
    be absent until first computed. This table is purely derived/disposable —
    it can be truncated at any time and will be repopulated lazily.
    """

    __tablename__ = "job_match_cache"
    __table_args__ = (
        UniqueConstraint("job_id", "profile_hash", name="ux_job_match_cache_job_profile"),
        Index("ix_job_match_cache_profile", "profile_hash"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid_mod.uuid4())
    )
    job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Tier-1 quick score (cheap model, batched on the list).
    quick_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quick_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # {"reasons": [...], "dealbreakers": [...]}
    quick_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quick_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Tier-2 deep analysis (advanced model, on demand): full DeepAnalysisResult.
    deep_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deep_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

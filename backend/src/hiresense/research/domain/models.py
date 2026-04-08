from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class CompanyResearch(Base):
    __tablename__ = "company_research"
    __table_args__ = (
        Index("ix_company_research_company_name", "company_name", unique=True),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    funding_stage: Mapped[str] = mapped_column(String(100), nullable=False)
    tech_stack: Mapped[str] = mapped_column(Text, nullable=False)
    culture_summary: Mapped[str] = mapped_column(Text, nullable=False)
    growth_trajectory: Mapped[str] = mapped_column(Text, nullable=False)
    red_flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    pros: Mapped[str] = mapped_column(Text, nullable=False)
    cons: Mapped[str] = mapped_column(Text, nullable=False)
    raw_llm_response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

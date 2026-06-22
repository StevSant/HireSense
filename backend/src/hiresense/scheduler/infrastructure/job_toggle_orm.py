from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class JobToggleOrm(Base):
    """Per-job enable/disable state. Absence of a row means "use the job's
    default_enabled"."""

    __tablename__ = "scheduler_job_toggles"

    job_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)

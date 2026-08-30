from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.shared.infrastructure.database import Base


class SubmissionEventOrm(Base):
    """One append-only entry on a submission attempt's audit tape.

    Never pruned on a retention timer, unlike the other operational tables in
    this project: this is the evidence trail for applications sent under the
    candidate's name, and silently deleting it would defeat its purpose.
    """

    __tablename__ = "submission_events"
    __table_args__ = (Index("ix_submission_events_attempt_seq", "attempt_id", "seq"),)

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    attempt_id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel

from hiresense.preference.domain.feedback_kind import FeedbackKind
from hiresense.preference.domain.feedback_source import FeedbackSource


class FeedbackSignal(BaseModel):
    """A single piece of feedback about a job (pure domain model)."""

    id: uuid_mod.UUID | None = None
    job_id: uuid_mod.UUID
    kind: FeedbackKind
    source: FeedbackSource
    job_embedding: list[float] | None = None
    # Per-dimension matching scores snapshotted at outcome time (implicit
    # signals only). None for explicit signals or when capture failed; such
    # signals contribute nothing to weight nudging.
    dimension_scores: dict[str, float] | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

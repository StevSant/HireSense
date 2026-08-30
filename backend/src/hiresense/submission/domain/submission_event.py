from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from hiresense.submission.domain.submission_event_kind import SubmissionEventKind


class SubmissionEvent(BaseModel):
    """One append-only entry on an attempt's audit tape.

    PII field values are recorded as a canonical key plus a value hash, never
    raw. Free-text screening answers ARE stored in full -- those are the
    sentences that went out under the candidate's name.
    """

    id: uuid_mod.UUID | None = None
    attempt_id: uuid_mod.UUID
    seq: int
    kind: SubmissionEventKind
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

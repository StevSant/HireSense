from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel

from hiresense.preference.domain import FeedbackKind


class FeedbackRequest(BaseModel):
    job_id: uuid_mod.UUID
    kind: FeedbackKind


class FeedbackSignalResponse(BaseModel):
    id: uuid_mod.UUID | None = None
    job_id: uuid_mod.UUID
    kind: FeedbackKind
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

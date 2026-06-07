from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UsageRecord:
    """Domain view of a single persisted LLM usage-log row."""

    feature_key: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    success: bool
    error: str | None = None
    user_id: str | None = None
    created_at: datetime | None = None
    id: uuid.UUID | None = None

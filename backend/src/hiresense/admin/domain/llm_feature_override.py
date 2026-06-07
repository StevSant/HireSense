from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class LLMFeatureOverrideRecord:
    """Domain view of a per-feature LLM config override.

    `provider` / `model` are nullable: ``None`` means "inherit from global".
    """

    feature_key: str
    provider: str | None
    model: str | None
    extra_params: dict = field(default_factory=dict)
    updated_by: str | None = None
    updated_at: datetime | None = None
    id: uuid.UUID | None = None

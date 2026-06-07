from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PreferenceModel(BaseModel):
    """The learned preference state: a decayed feedback delta vector.

    The taste vector is reconstructed at query time as
    ``normalize(alpha*baseline + delta_vector)`` against the live profile
    baseline, so this model stays tiny and re-anchors automatically when the
    profile changes.
    """

    delta_vector: list[float]
    # Phase 2: per-dimension integer weight deltas applied on top of each
    # scorer's base weight in the matching composite. Empty == no nudging
    # (cold-start / gate unmet), which reproduces today's scoring exactly.
    weight_overrides: dict[str, int] = Field(default_factory=dict)
    version: int = 1
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

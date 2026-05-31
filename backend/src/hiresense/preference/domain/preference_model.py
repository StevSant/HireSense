from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PreferenceModel(BaseModel):
    """The learned preference state: a decayed feedback delta vector.

    The taste vector is reconstructed at query time as
    ``normalize(alpha*baseline + delta_vector)`` against the live profile
    baseline, so this model stays tiny and re-anchors automatically when the
    profile changes.
    """

    delta_vector: list[float]
    version: int = 1
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

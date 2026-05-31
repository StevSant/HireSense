from __future__ import annotations

import enum

_NEGATIVE = frozenset({"thumbs_down", "not_interested", "rejected"})


class FeedbackKind(str, enum.Enum):
    # Explicit (Phase 1)
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    NOT_INTERESTED = "not_interested"
    MORE_LIKE_THIS = "more_like_this"

    @property
    def polarity(self) -> int:
        """+1 pulls the taste vector toward the job, -1 pushes away."""
        return -1 if self.value in _NEGATIVE else 1

    @property
    def weight_key(self) -> str:
        """Name of the Settings attribute holding this kind's magnitude."""
        return f"preference_weight_{self.value}"

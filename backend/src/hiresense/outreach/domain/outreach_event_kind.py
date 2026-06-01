from __future__ import annotations

import enum


class OutreachEventKind(str, enum.Enum):
    SENT = "sent"
    FOLLOWED_UP = "followed_up"
    REPLIED = "replied"

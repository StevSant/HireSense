from __future__ import annotations

import uuid
from typing import Protocol

from hiresense.tracking.domain.status_transition import StatusTransition


class StatusHistoryReadPort(Protocol):
    """Read access to application status history, consumed by analytics."""

    def list_history(self) -> list[StatusTransition]: ...

    def history_for(self, application_id: uuid.UUID) -> list[StatusTransition]: ...

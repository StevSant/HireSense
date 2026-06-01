from __future__ import annotations

import uuid
from typing import Protocol

from hiresense.outreach.domain import OutreachEvent


class OutreachRepositoryPort(Protocol):
    def add(self, event: OutreachEvent) -> OutreachEvent: ...

    def list_for(self, application_id: uuid.UUID) -> list[OutreachEvent]: ...

    def latest_for(self, application_id: uuid.UUID) -> OutreachEvent | None: ...

    def latest_per_application(self) -> list[OutreachEvent]: ...

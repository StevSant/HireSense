from __future__ import annotations

import uuid as uuid_mod
from typing import Protocol, runtime_checkable

from hiresense.inbox.domain.detected_signal import DetectedSignal
from hiresense.inbox.domain.signal_state import SignalState


@runtime_checkable
class DetectedSignalRepository(Protocol):
    def add(self, signal: DetectedSignal) -> DetectedSignal: ...

    def list(self, state: SignalState | None = None) -> list[DetectedSignal]: ...

    def get(self, id: uuid_mod.UUID) -> DetectedSignal | None: ...

    def set_state(self, id: uuid_mod.UUID, state: SignalState) -> DetectedSignal | None: ...

    def exists_message_id(self, message_id: str) -> bool: ...

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from hiresense.kernel.events import DomainEvent


class EventBus(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None: ...

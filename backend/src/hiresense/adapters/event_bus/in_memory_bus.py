from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

from hiresense.kernel.events import DomainEvent

logger = logging.getLogger(__name__)


class InMemoryEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[
            str, list[Callable[[DomainEvent], Awaitable[None]]]
        ] = defaultdict(list)

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            asyncio.create_task(self._safe_invoke(handler, event))

    async def _safe_invoke(
        self,
        handler: Callable[[DomainEvent], Awaitable[None]],
        event: DomainEvent,
    ) -> None:
        try:
            await handler(event)
        except Exception:
            logger.exception("Event handler failed for %s", event.event_type)

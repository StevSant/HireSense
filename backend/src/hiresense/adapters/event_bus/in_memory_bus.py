from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

from opentelemetry import trace

from hiresense.kernel.events import DomainEvent
from hiresense.observability import get_domain_metrics, get_tracer

_tracer = get_tracer("hiresense.events")

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
        metrics = get_domain_metrics()
        metrics.events_published_total.add(1, {"type": event.event_type})
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            asyncio.create_task(self._safe_invoke(handler, event))

    async def _safe_invoke(
        self,
        handler: Callable[[DomainEvent], Awaitable[None]],
        event: DomainEvent,
    ) -> None:
        with _tracer.start_as_current_span(
            "event.dispatch", attributes={"event.type": event.event_type}
        ) as span:
            try:
                await handler(event)
            except Exception:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                get_domain_metrics().event_handler_errors_total.add(
                    1, {"type": event.event_type}
                )
                logger.exception("Event handler failed for %s", event.event_type)

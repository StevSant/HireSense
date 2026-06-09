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
        # Strong references to in-flight handler tasks: the event loop only
        # holds weak refs, so without these the GC may drop a task mid-run.
        # They also let shutdown drain handlers instead of orphaning them.
        self._tasks: set[asyncio.Task[None]] = set()

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
            task = asyncio.create_task(self._safe_invoke(handler, event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def aclose(self, timeout: float = 5.0) -> None:
        """Drain in-flight handlers on shutdown; cancel stragglers after timeout."""
        pending = {task for task in self._tasks if not task.done()}
        if not pending:
            return
        _done, still_pending = await asyncio.wait(pending, timeout=timeout)
        for task in still_pending:
            logger.warning("Cancelling event handler still running at shutdown: %r", task)
            task.cancel()
        if still_pending:
            await asyncio.gather(*still_pending, return_exceptions=True)

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
            except Exception as exc:
                handler_name = getattr(handler, "__qualname__", repr(handler))
                logger.exception(
                    "Event handler %r failed for event %s",
                    handler_name,
                    event.event_type,
                )
                span.record_exception(exc)
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                get_domain_metrics().event_handler_errors_total.add(
                    1, {"type": event.event_type}
                )

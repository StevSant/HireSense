import asyncio

import pytest

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.kernel.events import DomainEvent


@pytest.mark.asyncio
async def test_publish_invokes_subscriber() -> None:
    bus = InMemoryEventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe("test.event", handler)
    event = DomainEvent(event_type="test.event", payload={"key": "value"})
    await bus.publish(event)
    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0].payload == {"key": "value"}


@pytest.mark.asyncio
async def test_publish_no_subscriber_does_not_raise() -> None:
    bus = InMemoryEventBus()
    event = DomainEvent(event_type="unhandled.event")
    await bus.publish(event)


@pytest.mark.asyncio
async def test_multiple_subscribers() -> None:
    bus = InMemoryEventBus()
    calls: list[str] = []

    async def handler_a(event: DomainEvent) -> None:
        calls.append("a")

    async def handler_b(event: DomainEvent) -> None:
        calls.append("b")

    bus.subscribe("multi.event", handler_a)
    bus.subscribe("multi.event", handler_b)
    await bus.publish(DomainEvent(event_type="multi.event"))
    await asyncio.sleep(0.05)
    assert sorted(calls) == ["a", "b"]

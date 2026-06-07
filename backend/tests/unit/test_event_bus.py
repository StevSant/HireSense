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
    event = DomainEvent(event_type="test.event")
    await bus.publish(event)
    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0].event_type == "test.event"


@pytest.mark.asyncio
async def test_publish_no_subscriber_does_not_raise() -> None:
    bus = InMemoryEventBus()
    event = DomainEvent(event_type="unhandled.event")
    await bus.publish(event)


@pytest.mark.asyncio
async def test_failing_handler_is_isolated_and_logged(caplog) -> None:
    """A throwing handler must not break the bus, and the log must name the
    failing handler and the event type (issue #43)."""
    bus = InMemoryEventBus()
    survived: list[str] = []

    async def failing_handler(event: DomainEvent) -> None:
        raise ValueError("boom")

    async def good_handler(event: DomainEvent) -> None:
        survived.append("ok")

    bus.subscribe("flaky.event", failing_handler)
    bus.subscribe("flaky.event", good_handler)
    with caplog.at_level("ERROR"):
        await bus.publish(DomainEvent(event_type="flaky.event"))
        await asyncio.sleep(0.05)

    # The healthy handler still ran despite the sibling raising.
    assert survived == ["ok"]
    # The error log identifies which handler failed and for which event.
    assert any(
        "failing_handler" in r.getMessage() and "flaky.event" in r.getMessage()
        for r in caplog.records
    )


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

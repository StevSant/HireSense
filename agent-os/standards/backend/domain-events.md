# Domain Events

Modules communicate asynchronously via domain events published through the `EventBus` port.

## Event Structure

All events extend `DomainEvent` with typed fields (no generic `payload: dict`):

```python
# kernel/events/jobs_ingested.py
class JobsIngestedEvent(DomainEvent):
    event_type: str = "jobs.ingested"
    job_ids: list[str]
    source: str
```

```python
# kernel/events/match_completed.py
class MatchCompletedEvent(DomainEvent):
    event_type: str = "match.completed"
    job_id: str
    match_id: str
    score: float
```

## Naming Convention

- `event_type` uses dotted string: `resource.action`
- Examples: `jobs.ingested`, `match.completed`, `profile.updated`
- One event class per file in `kernel/events/`

## Publishing

```python
event = JobsIngestedEvent(
    job_ids=["abc", "def"],
    source="remotive",
)
await self._event_bus.publish(event)
```

## Rules

- Events are immutable Pydantic models
- All fields typed — no `payload: dict`
- `timestamp` is auto-set (inherited from DomainEvent)
- Handlers are fire-and-forget via `asyncio.create_task`
- Event handlers must not raise — failures are logged

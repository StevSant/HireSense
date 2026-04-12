# Kernel & Shared Types

## Directory Layout

```
hiresense/
  kernel/
    schemas/       # Cross-module DTOs (Pydantic models)
    events/        # Domain events (extend DomainEvent)
    value_objects.py
  ports/           # Shared Protocol interfaces
    llm.py         # LLMPort
    event_bus.py   # EventBus
    vector_store.py
    latex_compiler.py
```

## kernel/schemas/

Cross-module Pydantic models for data that flows between modules:

```python
# kernel/schemas/ingestion.py
class NormalizedJobDTO(BaseModel):
    id: str
    title: str
    ...
```

- One DTO per file
- Only used for cross-module communication
- Module-internal models stay in `module/domain/`

## kernel/events/

Domain events extend `DomainEvent`:

```python
# kernel/events/jobs_ingested.py
class JobsIngestedEvent(DomainEvent):
    event_type: str = "jobs.ingested"
```

- One event per file
- Event type uses dotted string: `resource.action`
- Events are separate from DTOs

## ports/ (top-level)

Shared Protocol interfaces used across multiple modules:

```python
# ports/llm.py
class LLMPort(Protocol):
    async def complete(self, prompt: str, *,
                       system: str = "") -> str: ...
```

- Module-specific ports live in `module/ports/`
- Shared ports live in top-level `hiresense/ports/`
- Concrete adapters in `hiresense/adapters/` implement these ports

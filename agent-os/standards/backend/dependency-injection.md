# Dependency Injection

Use **Provider classes** + **app.state** with **ports & adapters**.
Routes depend on Protocol ports, not concrete classes.

## Module Provider

Each module defines a Provider that builds and caches service instances:

```python
# matching/provider.py
class MatchingProvider:
    def __init__(self, llm: LLMPort, event_bus: EventBus):
        self._orchestrator = MatchingOrchestrator(
            llm=llm, event_bus=event_bus
        )

    def get_orchestrator(self) -> MatchingOrchestrator:
        return self._orchestrator
```

## Wiring in main.py

Build concrete adapters and providers in `create_app()`, store on `app.state`:

```python
llm = AnthropicLLMAdapter(client=client, model=model)
app.state.matching = MatchingProvider(
    llm=llm, event_bus=bus
)
```

## Dependency Functions

Read from `request.app.state`:

```python
# matching/api/dependencies.py
def get_matching_orchestrator(
    request: Request,
) -> MatchingOrchestrator:
    return request.app.state.matching.get_orchestrator()
```

## Route Usage

```python
@router.post("/evaluate")
async def evaluate(
    orchestrator: Annotated[
        MatchingOrchestrator,
        Depends(get_matching_orchestrator)
    ],
): ...
```

## Rules

- No `raise NotImplementedError` stubs
- No `app.dependency_overrides` for production wiring
- Constructors accept ports (Protocols), not concrete adapter types
- One Provider per module
- Store all providers on `app.state`
- Tests create providers with test doubles directly

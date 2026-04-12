# LLM Scorer Pattern

All LLM-powered dimension scorers extend `BaseLLMScorer`.

## Abstract Methods

```python
class BaseLLMScorer(ABC):
    def __init__(self, llm: LLMPort, weight: int):
        ...

    @property
    @abstractmethod
    def dimension_name(self) -> str: ...

    @abstractmethod
    def _build_prompt(
        self, job: Any, profile: Any | None
    ) -> str: ...

    @abstractmethod
    def _output_schema(self) -> type[BaseModel]: ...
```

## Implementing a Scorer

```python
class SeniorityScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "seniority_fit"

    def _build_prompt(self, job, profile=None) -> str:
        return f"Analyze seniority for: {job}..."

    def _output_schema(self) -> type[BaseModel]:
        return DimensionResult
```

## Rules

- LLM dependency typed as `LLMPort`, not `Any`
- No `_build_system()` — system prompt is standardized in the base class
- Use structured output (Pydantic model) via `_output_schema()` — no multi-strategy JSON parsing
- Graceful degradation: returns `DimensionResult.default()` when LLM is `None`
- Scores clamped 0.0–1.0 via `DimensionResult` field validator
- One scorer per file

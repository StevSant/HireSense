from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol


class LLMPort(Protocol):
    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str: ...

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]: ...


@dataclass(frozen=True)
class LLMResult:
    """A completion plus the metadata a usage-tracking layer needs to record it."""

    content: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


class MeteredLLMPort(Protocol):
    """An LLM port that surfaces token/usage metadata.

    `generate()` returns the completion *and* the provider/model/token counts so a
    usage-tracking decorator can record usage without changing the public
    `LLMPort.complete() -> str` contract that domain code depends on.
    """

    async def generate(self, prompt: str, *, system: str = "", model: str = "") -> LLMResult: ...

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]: ...


class LLMInvocationError(RuntimeError):
    """Raised by a MeteredLLMPort when generation fails after config resolution.

    Carries the resolved provider/model so a usage-tracking decorator can record
    the failed call against the right buckets. The triggering exception is kept on
    `cause` (and chained as `__cause__`) so the decorator can re-raise it verbatim.
    """

    def __init__(self, *, provider: str, model: str, cause: BaseException) -> None:
        self.provider = provider
        self.model = model
        self.cause = cause
        super().__init__(str(cause))

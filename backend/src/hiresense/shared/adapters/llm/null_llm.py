from __future__ import annotations

from typing import AsyncIterator

from hiresense.shared.ports.llm_not_configured_error import LLMNotConfiguredError


class NullLLM:
    """`LLMPort` null object for when no LLM provider is configured.

    Collaborators depend on a plain `LLMPort` and are handed one of these
    instead of `None`, so the "no LLM" policy lives here rather than being
    re-invented as an `if self._llm is None:` branch at every call site.

    Every call raises `LLMNotConfiguredError` (a 503 at the API boundary). It
    never returns a stand-in completion: an invented answer is
    indistinguishable from a real one to the caller, gets persisted, and hides
    the missing configuration.

    `feature` is optional and only sharpens the error message — pass the same
    feature key used for the tracked adapter so the failure names what could
    not run.
    """

    def __init__(self, *, feature: str = "") -> None:
        self._feature = feature

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        raise LLMNotConfiguredError(self._message())

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]:
        # An async generator so it matches the real adapter's shape: callers
        # `async for` over it and the error surfaces on the first iteration.
        raise LLMNotConfiguredError(self._message())
        yield ""  # pragma: no cover - unreachable, makes this an async generator

    def _message(self) -> str:
        suffix = f" — {self._feature} is unavailable" if self._feature else ""
        return f"LLM not configured{suffix}"

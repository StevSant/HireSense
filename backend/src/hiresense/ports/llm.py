from __future__ import annotations

from typing import AsyncIterator, Protocol


class LLMPort(Protocol):
    async def complete(
        self, prompt: str, *, system: str = "", model: str = ""
    ) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def stream(
        self, prompt: str, *, system: str = ""
    ) -> AsyncIterator[str]: ...

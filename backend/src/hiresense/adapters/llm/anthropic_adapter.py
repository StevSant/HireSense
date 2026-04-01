from __future__ import annotations

from typing import Any, AsyncIterator


class AnthropicLLMAdapter:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        message = await self._client.messages.create(
            model=model or self._model,
            max_tokens=4096,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

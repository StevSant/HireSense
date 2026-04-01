from __future__ import annotations

from typing import Any


class OpenAIEmbeddingAdapter:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in response.data]

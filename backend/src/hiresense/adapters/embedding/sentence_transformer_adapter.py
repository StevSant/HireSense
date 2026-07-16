from __future__ import annotations

import asyncio
from typing import Any

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore[assignment,misc]


class SentenceTransformerAdapter:
    def __init__(self, model_name: str, device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model: Any = None
        self._model_lock = asyncio.Lock()

    def _load_model(self) -> Any:
        return SentenceTransformer(self._model_name, device=self._device)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            async with self._model_lock:
                if self._model is None:
                    self._model = await asyncio.to_thread(self._load_model)

        embeddings = await asyncio.to_thread(self._model.encode, texts)

        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return [list(e) for e in embeddings]

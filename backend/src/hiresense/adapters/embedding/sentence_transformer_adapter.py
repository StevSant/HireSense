from __future__ import annotations

import asyncio
import time
from typing import Any

from hiresense.observability import get_domain_metrics, get_tracer

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore[assignment,misc]

_tracer = get_tracer("hiresense.embedding")


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

        metrics = get_domain_metrics()
        started = time.perf_counter()
        # Span + histogram wrap the to_thread call itself (not the sync body)
        # so timing includes threadpool queueing, not just encode execution.
        with _tracer.start_as_current_span("embedding.encode") as span:
            span.set_attribute("batch_size", len(texts))
            embeddings = await asyncio.to_thread(self._model.encode, texts)
            metrics.embedding_encode_duration_ms.record((time.perf_counter() - started) * 1000.0)

        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return [list(e) for e in embeddings]

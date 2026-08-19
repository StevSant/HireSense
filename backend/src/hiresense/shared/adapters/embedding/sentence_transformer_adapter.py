from __future__ import annotations

import asyncio
import time
from functools import partial
from typing import Any

from hiresense.shared.observability import get_domain_metrics, get_tracer

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore[assignment,misc]

_tracer = get_tracer("hiresense.embedding")


class SentenceTransformerAdapter:
    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        *,
        batch_size: int = 64,
        torch_threads: int = 0,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._batch_size = max(1, batch_size)
        self._torch_threads = max(0, torch_threads)
        self._model: Any = None
        self._model_lock = asyncio.Lock()

    def _load_model(self) -> Any:
        if self._torch_threads:
            # Left unbounded, encode fans out over every core and starves the
            # event loop for the duration of a batch, so work that should overlap
            # with it (other sources' HTTP responses) stalls instead.
            try:
                import torch

                torch.set_num_threads(self._torch_threads)
            except Exception:  # pragma: no cover - torch always present with S-T
                pass
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
            embeddings = await asyncio.to_thread(
                partial(
                    self._model.encode,
                    texts,
                    batch_size=self._batch_size,
                    show_progress_bar=False,
                )
            )
            metrics.embedding_encode_duration_ms.record((time.perf_counter() - started) * 1000.0)

        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return [list(e) for e in embeddings]

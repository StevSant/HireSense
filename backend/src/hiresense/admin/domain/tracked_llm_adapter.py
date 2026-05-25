from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from hiresense.admin.domain.llm_config_service import LLMConfigService
from hiresense.admin.domain.llm_factory import LLMFactory
from hiresense.admin.domain.pricing import estimate_cost_usd
from hiresense.admin.domain.usage_recorder import UsageRecorder

logger = logging.getLogger(__name__)


class TrackedLLMAdapter:
    """LLMPort implementation that resolves config per-call and records usage.

    One instance is built per feature; `feature_key` is fixed at construction
    time. Every call:
      1) asks `LLMConfigService` for the effective config (override -> global -> env)
      2) asks `LLMFactory` for a cached LangChain chat model
      3) invokes and records tokens/cost/latency to `UsageRecorder`

    Hot-reload works because step (1) re-reads on every call (subject to a
    short TTL cache that the admin endpoints invalidate after each write).
    """

    def __init__(
        self,
        *,
        config_service: LLMConfigService,
        factory: LLMFactory,
        recorder: UsageRecorder,
        feature_key: str,
    ) -> None:
        self._config_service = config_service
        self._factory = factory
        self._recorder = recorder
        self._feature_key = feature_key

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        config = self._config_service.resolve(self._feature_key)
        chat_model = self._factory.build_chat_model(config)
        messages: list[Any] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        target = chat_model.bind(model=model) if model else chat_model
        effective_model = model or config.model

        t0 = time.perf_counter()
        try:
            response = await target.ainvoke(messages)
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            self._recorder.record(
                feature_key=self._feature_key,
                provider=config.provider,
                model=effective_model,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                success=False,
                error=str(exc)[:500],
                user_id=None,
            )
            raise

        latency_ms = (time.perf_counter() - t0) * 1000.0
        usage = getattr(response, "usage_metadata", None) or {}
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
        cost_usd = estimate_cost_usd(config.provider, effective_model, input_tokens, output_tokens)
        self._recorder.record(
            feature_key=self._feature_key,
            provider=config.provider,
            model=effective_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            success=True,
            error=None,
            user_id=None,
        )
        return response.content

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]:
        # Streaming is rare in this app; we don't record token counts here because
        # LangChain only emits usage_metadata on the final chunk for some providers.
        # If usage tracking on streams becomes important, accumulate from the final
        # chunk's response_metadata.usage.
        config = self._config_service.resolve(self._feature_key)
        chat_model = self._factory.build_chat_model(config)
        messages: list[Any] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        async for chunk in chat_model.astream(messages):
            if chunk.content:
                yield chunk.content

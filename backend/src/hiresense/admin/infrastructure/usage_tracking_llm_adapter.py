from __future__ import annotations

import time
from typing import TYPE_CHECKING, AsyncIterator

# Direct-submodule import (not `from hiresense.admin.domain import ...`) to avoid
# closing the admin.domain -> admin.ports -> admin.infrastructure import cycle.
from hiresense.admin.domain.pricing import estimate_cost_usd
from hiresense.ports.llm import LLMInvocationError, MeteredLLMPort

if TYPE_CHECKING:
    from hiresense.admin.domain import UsageRecorder


class UsageTrackingLLMAdapter:
    """LLMPort decorator that records token usage, cost, and latency per call.

    Wraps any `MeteredLLMPort`: on success it records the result's token counts and
    the estimated cost; on failure it records a zero-token failure row and re-raises
    the original exception, so domain callers behave exactly as they did before.
    Streaming is delegated without recording (LangChain only emits usage metadata on
    the final chunk for some providers).
    """

    def __init__(
        self,
        inner: MeteredLLMPort,
        *,
        recorder: UsageRecorder,
        feature_key: str,
    ) -> None:
        self._inner = inner
        self._recorder = recorder
        self._feature_key = feature_key

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        t0 = time.perf_counter()
        try:
            result = await self._inner.generate(prompt, system=system, model=model)
        except LLMInvocationError as err:
            self._recorder.record(
                feature_key=self._feature_key,
                provider=err.provider,
                model=err.model,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                success=False,
                error=str(err.cause)[:500],
                user_id=None,
            )
            raise err.cause

        cost_usd = estimate_cost_usd(
            result.provider, result.model, result.input_tokens, result.output_tokens
        )
        self._recorder.record(
            feature_key=self._feature_key,
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            cost_usd=cost_usd,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            success=True,
            error=None,
            user_id=None,
        )
        return result.content

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]:
        async for chunk in self._inner.stream(prompt, system=system):
            yield chunk

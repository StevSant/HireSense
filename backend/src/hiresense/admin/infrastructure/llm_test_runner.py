from __future__ import annotations

import time

from langchain_core.messages import HumanMessage

from hiresense.admin.domain.resolved_config import ResolvedConfig
from hiresense.admin.domain.test_result import TestResult
from hiresense.admin.infrastructure.llm_factory import LLMFactory, UnsupportedProviderError


class LLMTestRunner:
    """Validates a ResolvedConfig by issuing one tiny call.

    Used both by `POST /admin/llm-settings/test` and as a guard before
    persisting `PUT /admin/llm-settings`.
    """

    _PING_PROMPT = "Reply with the single word: pong"

    def __init__(self, factory: LLMFactory) -> None:
        self._factory = factory

    async def run(self, config: ResolvedConfig) -> TestResult:
        try:
            chat_model = self._factory.build_chat_model(config)
        except UnsupportedProviderError as exc:
            return TestResult(success=False, latency_ms=0.0, response_preview="", error=str(exc))

        t0 = time.perf_counter()
        try:
            response = await chat_model.ainvoke([HumanMessage(content=self._PING_PROMPT)])
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return TestResult(
                success=False, latency_ms=latency_ms, response_preview="", error=str(exc)[:500]
            )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        content = str(getattr(response, "content", "") or "")[:200]
        return TestResult(success=True, latency_ms=latency_ms, response_preview=content, error=None)

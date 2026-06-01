from __future__ import annotations

import asyncio
import logging

from hiresense.admin.ports import LLMUsageLogRepositoryPort
from hiresense.observability import get_domain_metrics

logger = logging.getLogger(__name__)


class UsageRecorder:
    """Persists usage rows off the request hot-path.

    The DB write is dispatched to a background task so a slow insert never
    blocks the response. Failures are logged but never raised — losing a
    usage row is preferable to failing the user's LLM call.
    """

    def __init__(self, repo: LLMUsageLogRepositoryPort) -> None:
        self._repo = repo

    def record(
        self,
        *,
        feature_key: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        latency_ms: float,
        success: bool,
        error: str | None,
        user_id: str | None,
    ) -> None:
        try:
            m = get_domain_metrics()
            m.llm_tokens_total.add(input_tokens, {"type": "input", "model": model})
            m.llm_tokens_total.add(output_tokens, {"type": "output", "model": model})
            m.llm_cost_usd_total.add(cost_usd, {"model": model, "feature": feature_key})
            m.llm_call_duration_ms.record(latency_ms, {"model": model})
            if not success:
                m.llm_errors_total.add(1, {"model": model, "feature": feature_key})
        except Exception:  # pragma: no cover - telemetry must never break recording
            logger.debug("LLM metric recording failed", exc_info=True)

        async def _persist() -> None:
            try:
                await asyncio.to_thread(
                    self._repo.insert,
                    feature_key=feature_key,
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    success=success,
                    error=error,
                    user_id=user_id,
                )
            except Exception as exc:
                logger.warning("usage log insert failed: %s", exc)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_persist())
        except RuntimeError:
            # No running loop (e.g., sync test path). Write inline.
            try:
                self._repo.insert(
                    feature_key=feature_key,
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    success=success,
                    error=error,
                    user_id=user_id,
                )
            except Exception as exc:
                logger.warning("usage log insert failed (sync path): %s", exc)

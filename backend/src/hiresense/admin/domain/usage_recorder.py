from __future__ import annotations

import asyncio
import logging

from hiresense.admin.infrastructure.llm_usage_log_repository import LLMUsageLogRepository

logger = logging.getLogger(__name__)


class UsageRecorder:
    """Persists usage rows off the request hot-path.

    The DB write is dispatched to a background task so a slow insert never
    blocks the response. Failures are logged but never raised — losing a
    usage row is preferable to failing the user's LLM call.
    """

    def __init__(self, repo: LLMUsageLogRepository) -> None:
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

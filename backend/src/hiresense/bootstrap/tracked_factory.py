from __future__ import annotations

from collections.abc import Callable

from hiresense.admin.domain import (
    LLMConfigService,
    LLMFactory,
    TrackedLLMAdapter,
    UsageRecorder,
)
from hiresense.config import Settings


def make_tracked(
    *,
    config_service: LLMConfigService,
    factory: LLMFactory,
    recorder: UsageRecorder,
    settings: Settings,
) -> Callable[[str], TrackedLLMAdapter | None]:
    """Build the per-feature tracked-LLM factory.

    Returns a callable that yields a usage-tracking LLM adapter for a feature
    key, or None when no API key is configured (so features degrade gracefully).
    """

    def _tracked(feature_key: str) -> TrackedLLMAdapter | None:
        if not settings.llm_api_key:
            return None
        return TrackedLLMAdapter(
            config_service=config_service,
            factory=factory,
            recorder=recorder,
            feature_key=feature_key,
        )

    return _tracked

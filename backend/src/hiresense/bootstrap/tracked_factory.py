from __future__ import annotations

from collections.abc import Callable

from hiresense.admin.domain import LLMConfigService, UsageRecorder
from hiresense.admin.infrastructure import LLMFactory
from hiresense.admin.infrastructure import (
    FeatureConfiguredLLMAdapter,
    UsageTrackingLLMAdapter,
)
from hiresense.config import Settings
from hiresense.ports import LLMPort


def make_tracked(
    *,
    config_service: LLMConfigService,
    factory: LLMFactory,
    recorder: UsageRecorder,
    settings: Settings,
) -> Callable[[str], LLMPort | None]:
    """Build the per-feature tracked-LLM factory.

    Returns a callable that yields a usage-tracking LLM adapter for a feature key,
    or None when no API key is configured (so features degrade gracefully). The
    adapter is a `UsageTrackingLLMAdapter` decorating a `FeatureConfiguredLLMAdapter`
    decorating a `LangChainLLMAdapter`.
    """

    def _tracked(feature_key: str) -> LLMPort | None:
        if not settings.llm_api_key:
            return None
        configured = FeatureConfiguredLLMAdapter(
            config_service=config_service,
            factory=factory,
            feature_key=feature_key,
            cache_prompt_enabled=settings.llm_prompt_cache_enabled,
        )
        return UsageTrackingLLMAdapter(configured, recorder=recorder, feature_key=feature_key)

    return _tracked

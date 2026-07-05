from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

from hiresense.adapters.llm import LangChainLLMAdapter
from hiresense.ports.llm import LLMInvocationError, LLMResult

if TYPE_CHECKING:
    from hiresense.admin.domain import LLMConfigService
    from hiresense.admin.domain.resolved_config import ResolvedConfig
    from hiresense.admin.ports import LLMFactoryPort


class FeatureConfiguredLLMAdapter:
    """MeteredLLMPort that resolves the effective per-feature config on every call.

    Resolving per call (subject to the config service's short TTL cache) is what
    enables hot-reload: an admin settings change takes effect on the next call. The
    actual LangChain invocation is delegated to a `LangChainLLMAdapter`, built with
    the resolved provider/model so the returned `LLMResult` is attributable.
    """

    def __init__(
        self,
        *,
        config_service: LLMConfigService,
        factory: LLMFactoryPort,
        feature_key: str,
    ) -> None:
        self._config_service = config_service
        self._factory = factory
        self._feature_key = feature_key

    async def generate(self, prompt: str, *, system: str = "", model: str = "") -> LLMResult:
        config = self._config_service.resolve(self._feature_key)
        try:
            inner = self._build_inner(config)
            return await inner.generate(prompt, system=system, model=model)
        except Exception as exc:
            raise LLMInvocationError(
                provider=config.provider, model=model or config.model, cause=exc
            ) from exc

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]:
        config = self._config_service.resolve(self._feature_key)
        inner = self._build_inner(config)
        async for chunk in inner.stream(prompt, system=system):
            yield chunk

    def _build_inner(self, config: ResolvedConfig) -> LangChainLLMAdapter:
        chat_model = self._factory.build_chat_model(config)
        return LangChainLLMAdapter(chat_model, provider=config.provider, model_name=config.model)

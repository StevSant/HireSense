from __future__ import annotations

from typing import Any, AsyncIterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from hiresense.ports.llm import LLMResult


class LangChainLLMAdapter:
    """LLMPort + MeteredLLMPort over a LangChain BaseChatModel.

    `provider` / `model_name` describe the wrapped model so `generate()` can report
    them in the LLMResult (used downstream for cost attribution). They default to
    empty for plain static use; the config-resolving adapter passes the resolved
    values so usage can be attributed to the right provider/model.
    """

    def __init__(
        self,
        model: BaseChatModel,
        *,
        provider: str = "",
        model_name: str = "",
        cache_system_prefix: bool = False,
    ) -> None:
        self._model = model
        self._provider = provider
        self._model_name = model_name
        # When True, the system prompt is sent as an Anthropic content block
        # with `cache_control: ephemeral` so a stable prefix (static
        # instructions + byte-stable candidate block) is cached server-side
        # across calls. Only meaningful for the Anthropic provider — callers
        # are responsible for only setting this when config.provider is
        # "anthropic" (see FeatureConfiguredLLMAdapter).
        self._cache_system_prefix = cache_system_prefix

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        result = await self.generate(prompt, system=system, model=model)
        return result.content

    async def generate(self, prompt: str, *, system: str = "", model: str = "") -> LLMResult:
        messages = self._messages(prompt, system)
        target = self._model.bind(model=model) if model else self._model
        response = await target.ainvoke(messages)

        usage = getattr(response, "usage_metadata", None) or {}
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
        return LLMResult(
            content=response.content,
            provider=self._provider,
            model=model or self._model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]:
        messages = self._messages(prompt, system)
        async for chunk in self._model.astream(messages):
            if chunk.content:
                yield chunk.content

    def _messages(self, prompt: str, system: str) -> list[Any]:
        messages: list[Any] = []
        if system:
            messages.append(self._system_message(system))
        messages.append(HumanMessage(content=prompt))
        return messages

    def _system_message(self, system: str) -> SystemMessage:
        if not self._cache_system_prefix:
            return SystemMessage(content=system)
        # Content-block form: langchain_anthropic passes cache_control through
        # verbatim on system content blocks (see ChatAnthropic._format_messages),
        # which is what makes the Anthropic API cache this prefix server-side.
        return SystemMessage(
            content=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        )

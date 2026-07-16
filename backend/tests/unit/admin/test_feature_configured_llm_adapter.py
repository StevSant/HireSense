from __future__ import annotations

from dataclasses import dataclass

import pytest

from hiresense.admin.domain.resolved_config import ResolvedConfig
from hiresense.admin.infrastructure import FeatureConfiguredLLMAdapter


@dataclass
class _FakeResponse:
    content: str
    usage_metadata: dict | None = None


class _FakeChatModel:
    """Records the messages it was invoked with (mirrors LangChain's shape)."""

    def __init__(self, response: _FakeResponse | None = None) -> None:
        self._response = response or _FakeResponse(content="ok")
        self.calls: list[list] = []

    def bind(self, **_kwargs):
        return self

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return self._response


class _FakeConfigService:
    def __init__(self, config: ResolvedConfig) -> None:
        self._config = config

    def resolve(self, _feature_key: str) -> ResolvedConfig:
        return self._config


class _FakeFactory:
    def __init__(self, chat_model: _FakeChatModel) -> None:
        self._chat_model = chat_model

    def build_chat_model(self, _config: ResolvedConfig):
        return self._chat_model


def _config(provider: str) -> ResolvedConfig:
    return ResolvedConfig(
        provider=provider, model="m", api_key="k", extra_params={}, source="global"
    )


@pytest.mark.asyncio
async def test_anthropic_provider_gets_cache_control_when_enabled() -> None:
    chat = _FakeChatModel()
    adapter = FeatureConfiguredLLMAdapter(
        config_service=_FakeConfigService(_config("anthropic")),
        factory=_FakeFactory(chat),
        feature_key="match_quick_scorer",
        cache_prompt_enabled=True,
    )

    await adapter.generate("hi", system="be nice")

    system_message = chat.calls[0][0]
    assert system_message.content == [
        {"type": "text", "text": "be nice", "cache_control": {"type": "ephemeral"}}
    ]


@pytest.mark.asyncio
async def test_non_anthropic_provider_never_gets_cache_control() -> None:
    chat = _FakeChatModel()
    adapter = FeatureConfiguredLLMAdapter(
        config_service=_FakeConfigService(_config("openai")),
        factory=_FakeFactory(chat),
        feature_key="match_quick_scorer",
        cache_prompt_enabled=True,
    )

    await adapter.generate("hi", system="be nice")

    system_message = chat.calls[0][0]
    assert system_message.content == "be nice"


@pytest.mark.asyncio
async def test_cache_prompt_disabled_gate_suppresses_cache_control_even_on_anthropic() -> None:
    chat = _FakeChatModel()
    adapter = FeatureConfiguredLLMAdapter(
        config_service=_FakeConfigService(_config("anthropic")),
        factory=_FakeFactory(chat),
        feature_key="match_quick_scorer",
        cache_prompt_enabled=False,
    )

    await adapter.generate("hi", system="be nice")

    system_message = chat.calls[0][0]
    assert system_message.content == "be nice"


@pytest.mark.asyncio
async def test_cache_prompt_enabled_defaults_to_true() -> None:
    chat = _FakeChatModel()
    adapter = FeatureConfiguredLLMAdapter(
        config_service=_FakeConfigService(_config("anthropic")),
        factory=_FakeFactory(chat),
        feature_key="match_quick_scorer",
    )

    await adapter.generate("hi", system="be nice")

    system_message = chat.calls[0][0]
    assert system_message.content == [
        {"type": "text", "text": "be nice", "cache_control": {"type": "ephemeral"}}
    ]

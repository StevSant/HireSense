from __future__ import annotations

from dataclasses import dataclass

import pytest

from hiresense.admin.domain.resolved_config import ResolvedConfig
from hiresense.admin.infrastructure import (
    FeatureConfiguredLLMAdapter,
    UsageTrackingLLMAdapter,
)


@dataclass
class _FakeResponse:
    content: str
    usage_metadata: dict | None


class _FakeChatModel:
    def __init__(
        self, response: _FakeResponse | None = None, raise_exc: Exception | None = None
    ) -> None:
        self._response = response
        self._raise = raise_exc
        self.calls: list[list] = []

    def bind(self, **_kwargs):
        return self

    async def ainvoke(self, messages):
        self.calls.append(messages)
        if self._raise is not None:
            raise self._raise
        return self._response


@dataclass
class _FakeRecord:
    feature_key: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    success: bool
    error: str | None
    user_id: str | None


class _FakeRecorder:
    def __init__(self) -> None:
        self.records: list[_FakeRecord] = []

    def record(self, **kwargs) -> None:
        self.records.append(_FakeRecord(**kwargs))


class _FakeConfigService:
    def __init__(self, config: ResolvedConfig) -> None:
        self._config = config

    def resolve(self, _feature_key: str) -> ResolvedConfig:
        return self._config


class _FakeFactory:
    def __init__(self, chat_model) -> None:
        self._chat_model = chat_model

    def build_chat_model(self, _config: ResolvedConfig):
        return self._chat_model


def _build(config: ResolvedConfig, chat, recorder, feature_key: str) -> UsageTrackingLLMAdapter:
    configured = FeatureConfiguredLLMAdapter(
        config_service=_FakeConfigService(config),
        factory=_FakeFactory(chat),
        feature_key=feature_key,
    )
    return UsageTrackingLLMAdapter(configured, recorder=recorder, feature_key=feature_key)


@pytest.mark.asyncio
async def test_success_records_token_counts_and_cost() -> None:
    config = ResolvedConfig(
        provider="anthropic",
        model="claude-sonnet-4-6",
        api_key="k",
        extra_params={},
        source="global",
    )
    chat = _FakeChatModel(
        response=_FakeResponse(
            content="hello",
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        ),
    )
    recorder = _FakeRecorder()
    adapter = _build(config, chat, recorder, "cv_parser")

    result = await adapter.complete("hi", system="sys")
    assert result == "hello"
    assert len(recorder.records) == 1
    rec = recorder.records[0]
    assert rec.feature_key == "cv_parser"
    assert rec.provider == "anthropic"
    assert rec.model == "claude-sonnet-4-6"
    assert rec.input_tokens == 100
    assert rec.output_tokens == 50
    assert rec.total_tokens == 150
    assert rec.success is True
    assert rec.error is None
    # sonnet pricing: 100/1M * 3 + 50/1M * 15 = 0.0003 + 0.00075 = 0.00105
    assert rec.cost_usd == pytest.approx(0.00105, rel=1e-6)


@pytest.mark.asyncio
async def test_error_path_records_failure_and_reraises_original() -> None:
    config = ResolvedConfig(
        provider="anthropic",
        model="claude-sonnet-4-6",
        api_key="k",
        extra_params={},
        source="global",
    )
    chat = _FakeChatModel(raise_exc=RuntimeError("api outage"))
    recorder = _FakeRecorder()
    adapter = _build(config, chat, recorder, "culture_scorer")

    with pytest.raises(RuntimeError, match="api outage"):
        await adapter.complete("hi")
    assert len(recorder.records) == 1
    rec = recorder.records[0]
    assert rec.success is False
    assert rec.provider == "anthropic"
    assert rec.model == "claude-sonnet-4-6"
    assert rec.error is not None and "api outage" in rec.error
    assert rec.input_tokens == 0 and rec.output_tokens == 0


@pytest.mark.asyncio
async def test_missing_usage_metadata_records_zero_tokens() -> None:
    config = ResolvedConfig(
        provider="anthropic",
        model="claude-sonnet-4-6",
        api_key="k",
        extra_params={},
        source="global",
    )
    chat = _FakeChatModel(response=_FakeResponse(content="ok", usage_metadata=None))
    recorder = _FakeRecorder()
    adapter = _build(config, chat, recorder, "cv_parser")

    result = await adapter.complete("hi")
    assert result == "ok"
    rec = recorder.records[0]
    assert rec.input_tokens == 0
    assert rec.output_tokens == 0
    assert rec.cost_usd == 0.0
    assert rec.success is True

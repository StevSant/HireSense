import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from hiresense.adapters.llm import LangChainLLMAdapter
from hiresense.ports import LLMPort, LLMTimeoutError


def test_adapter_satisfies_llm_port() -> None:
    mock_model = MagicMock()
    adapter: LLMPort = LangChainLLMAdapter(model=mock_model)
    assert hasattr(adapter, "complete")
    assert hasattr(adapter, "stream")


@pytest.mark.asyncio
async def test_complete_invokes_model() -> None:
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="Hello from LangChain")

    adapter = LangChainLLMAdapter(model=mock_model)
    result = await adapter.complete("Say hello", system="Be friendly")

    assert result == "Hello from LangChain"
    mock_model.ainvoke.assert_called_once()
    call_args = mock_model.ainvoke.call_args[0][0]
    assert len(call_args) == 2  # system + human messages


@pytest.mark.asyncio
async def test_complete_with_model_override() -> None:
    mock_model = MagicMock()
    bound_model = AsyncMock()
    bound_model.ainvoke.return_value = AIMessage(content="response")
    mock_model.bind.return_value = bound_model

    adapter = LangChainLLMAdapter(model=mock_model)
    result = await adapter.complete("prompt", model="claude-opus-4-6")

    mock_model.bind.assert_called_once_with(model="claude-opus-4-6")
    assert result == "response"


@pytest.mark.asyncio
async def test_complete_without_system_prompt() -> None:
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="response")

    adapter = LangChainLLMAdapter(model=mock_model)
    await adapter.complete("prompt")

    call_args = mock_model.ainvoke.call_args[0][0]
    assert len(call_args) == 1  # only human message, no system


@pytest.mark.asyncio
async def test_cache_system_prefix_adds_cache_control_block() -> None:
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="response")

    adapter = LangChainLLMAdapter(model=mock_model, cache_system_prefix=True)
    await adapter.complete("prompt", system="You are a helpful assistant")

    call_args = mock_model.ainvoke.call_args[0][0]
    system_message = call_args[0]
    assert system_message.content == [
        {
            "type": "text",
            "text": "You are a helpful assistant",
            "cache_control": {"type": "ephemeral"},
        }
    ]


@pytest.mark.asyncio
async def test_cache_system_prefix_disabled_by_default() -> None:
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="response")

    adapter = LangChainLLMAdapter(model=mock_model)
    await adapter.complete("prompt", system="You are a helpful assistant")

    call_args = mock_model.ainvoke.call_args[0][0]
    system_message = call_args[0]
    assert system_message.content == "You are a helpful assistant"


@pytest.mark.asyncio
async def test_cache_system_prefix_true_but_no_system_prompt_sends_no_system_message() -> None:
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="response")

    adapter = LangChainLLMAdapter(model=mock_model, cache_system_prefix=True)
    await adapter.complete("prompt")

    call_args = mock_model.ainvoke.call_args[0][0]
    assert len(call_args) == 1  # only the human message


@pytest.mark.asyncio
async def test_generate_raises_llm_timeout_error_when_call_exceeds_timeout() -> None:
    mock_model = AsyncMock()

    async def slow_ainvoke(_messages):
        await asyncio.sleep(1.0)
        return AIMessage(content="too late")

    mock_model.ainvoke = slow_ainvoke

    adapter = LangChainLLMAdapter(model=mock_model, provider="anthropic", timeout=0.01)
    with pytest.raises(LLMTimeoutError) as excinfo:
        await adapter.complete("prompt")
    assert excinfo.value.timeout == 0.01
    assert excinfo.value.provider == "anthropic"


@pytest.mark.asyncio
async def test_generate_returns_before_timeout() -> None:
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="fast enough")

    adapter = LangChainLLMAdapter(model=mock_model, timeout=5.0)
    result = await adapter.complete("prompt")

    assert result == "fast enough"


@pytest.mark.asyncio
async def test_no_timeout_when_timeout_is_none() -> None:
    # With timeout=None (the default) the call is not wrapped in wait_for; a
    # completed call returns normally regardless of the (absent) ceiling.
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="response")

    adapter = LangChainLLMAdapter(model=mock_model)
    result = await adapter.complete("prompt")

    assert result == "response"


@pytest.mark.asyncio
async def test_stream_yields_chunks() -> None:
    mock_model = AsyncMock()

    async def fake_stream(messages):
        for chunk in [
            MagicMock(content="Hello"),
            MagicMock(content=" world"),
        ]:
            yield chunk

    mock_model.astream = fake_stream

    adapter = LangChainLLMAdapter(model=mock_model)
    chunks = []
    async for chunk in adapter.stream("Say hello"):
        chunks.append(chunk)

    assert chunks == ["Hello", " world"]

import pytest

from hiresense.adapters.llm.anthropic_adapter import AnthropicLLMAdapter
from hiresense.adapters.llm.openai_embeddings import OpenAIEmbeddingAdapter


class FakeAnthropicMessage:
    def __init__(self, text: str) -> None:
        self.content = [type("Block", (), {"text": text})()]


class FakeAnthropicClient:
    class messages:
        @staticmethod
        async def create(**kwargs) -> "FakeAnthropicMessage":
            return FakeAnthropicMessage("Hello from Claude")


class FakeEmbeddingData:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class FakeEmbeddingResponse:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self.data = [FakeEmbeddingData(e) for e in embeddings]


class FakeOpenAIClient:
    class embeddings:
        @staticmethod
        async def create(**kwargs) -> "FakeEmbeddingResponse":
            return FakeEmbeddingResponse([[0.1, 0.2, 0.3] for _ in kwargs["input"]])


@pytest.mark.asyncio
async def test_anthropic_adapter_complete() -> None:
    adapter = AnthropicLLMAdapter(
        client=FakeAnthropicClient(),
        model="claude-sonnet-4-6",
    )
    result = await adapter.complete("Hello", system="Be helpful")
    assert result == "Hello from Claude"


@pytest.mark.asyncio
async def test_openai_embedding_adapter() -> None:
    adapter = OpenAIEmbeddingAdapter(
        client=FakeOpenAIClient(),
        model="text-embedding-3-small",
    )
    result = await adapter.embed(["hello", "world"])
    assert len(result) == 2
    assert len(result[0]) == 3
    assert result[0] == [0.1, 0.2, 0.3]

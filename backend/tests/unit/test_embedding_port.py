import pytest

from hiresense.ports import EmbeddingPort


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


@pytest.mark.asyncio
async def test_fake_embedder_satisfies_embedding_port() -> None:
    embedder: EmbeddingPort = FakeEmbedder()
    result = await embedder.embed(["hello", "world"])
    assert len(result) == 2
    assert result[0] == [0.1, 0.2]

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from hiresense.adapters.embedding import SentenceTransformerAdapter
from hiresense.ports import EmbeddingPort


def test_adapter_satisfies_embedding_port() -> None:
    adapter: EmbeddingPort = SentenceTransformerAdapter(model_name="all-mpnet-base-v2")
    assert hasattr(adapter, "embed")


@pytest.mark.asyncio
async def test_embed_delegates_to_sentence_transformer() -> None:
    adapter = SentenceTransformerAdapter(model_name="all-mpnet-base-v2")

    fake_model = MagicMock()
    fake_model.encode.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    adapter._model = fake_model

    result = await adapter.embed(["hello", "world"])

    fake_model.encode.assert_called_once_with(["hello", "world"])
    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


@pytest.mark.asyncio
async def test_embed_lazy_loads_model() -> None:
    with patch(
        "hiresense.adapters.embedding.sentence_transformer_adapter.SentenceTransformer"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_instance.encode.return_value = [[0.1]]
        mock_cls.return_value = mock_instance

        adapter = SentenceTransformerAdapter(model_name="all-mpnet-base-v2", device="cpu")
        assert adapter._model is None

        await adapter.embed(["test"])

        mock_cls.assert_called_once_with("all-mpnet-base-v2", device="cpu")
        assert adapter._model is mock_instance


@pytest.mark.asyncio
async def test_concurrent_first_calls_load_model_exactly_once() -> None:
    # Two concurrent cold `embed()` calls must not each load the ~420MB
    # model — the asyncio.Lock double-checked load must serialize them so
    # the second waiter observes the already-loaded model.
    load_calls = 0

    class _FakeModel:
        def encode(self, texts):
            return [[0.1] for _ in texts]

    def fake_load():
        nonlocal load_calls
        load_calls += 1
        return _FakeModel()

    adapter = SentenceTransformerAdapter(model_name="all-mpnet-base-v2")
    adapter._load_model = fake_load

    results = await asyncio.gather(adapter.embed(["a"]), adapter.embed(["b"]))

    assert load_calls == 1
    assert results == [[[0.1]], [[0.1]]]


@pytest.mark.asyncio
async def test_embed_converts_numpy_to_list() -> None:
    adapter = SentenceTransformerAdapter(model_name="all-mpnet-base-v2")

    fake_model = MagicMock()
    # sentence-transformers returns numpy arrays; simulate with objects that have .tolist()
    import numpy as np

    fake_model.encode.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])
    adapter._model = fake_model

    result = await adapter.embed(["a", "b"])

    assert isinstance(result, list)
    assert isinstance(result[0], list)
    assert result[0] == pytest.approx([0.1, 0.2])

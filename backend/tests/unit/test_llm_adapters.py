from hiresense.adapters.embedding import SentenceTransformerAdapter
from hiresense.adapters.llm import LangChainLLMAdapter


def test_langchain_adapter_exported_from_package() -> None:
    assert LangChainLLMAdapter is not None


def test_sentence_transformer_adapter_exported_from_package() -> None:
    assert SentenceTransformerAdapter is not None

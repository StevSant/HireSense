from hiresense.adapters.vector_store.pgvector_adapter import _parse_vector


def test_parse_bracketed_vector() -> None:
    assert _parse_vector("[0.1,0.2,0.3]") == [0.1, 0.2, 0.3]


def test_parse_handles_spaces() -> None:
    assert _parse_vector("[1, 2, 3]") == [1.0, 2.0, 3.0]


def test_parse_empty_returns_empty() -> None:
    assert _parse_vector("[]") == []
